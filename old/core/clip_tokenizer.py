# core/clip_tokenizer.py

import os
import gzip
import html
import urllib.request
import logging
from functools import lru_cache

logger = logging.getLogger(__name__)

# Полностью публичный URL без ограничений авторизации
VOCAB_URL = "https://raw.githubusercontent.com/openai/CLIP/main/clip/bpe_simple_vocab_16e6.txt.gz"

@lru_cache()
def bytes_to_unicode():
    bs = list(range(ord("!"), ord("~")+1)) + list(range(ord("¡"), ord("¬")+1)) + list(range(ord("®"), ord("ÿ")+1))
    cs = bs[:]
    n = 0
    for b in range(2**8):
        if b not in bs:
            bs.append(b)
            cs.append(2**8+n)
            n += 1
    cs = [chr(n) for n in cs]
    return dict(zip(bs, cs))

def get_pairs(word):
    pairs = set()
    prev_char = word[0]
    for char in word[1:]:
        pairs.add((prev_char, char))
        prev_char = char
    return pairs

class SimpleTokenizer:
    def __init__(self):
        models_dir = os.path.join(os.path.dirname(__file__), "..", "assets", "models")
        os.makedirs(models_dir, exist_ok=True)
        self.vocab_path = os.path.join(models_dir, "bpe_simple_vocab_16e6.txt.gz")
        
        if not os.path.exists(self.vocab_path) or os.path.getsize(self.vocab_path) < 1000:
            logger.info("Скачивание словаря BPE для CLIP...")
            try:
                urllib.request.urlretrieve(VOCAB_URL, self.vocab_path)
            except Exception as e:
                logger.error(f"Не удалось скачать словарь: {e}")
                
        self.byte_encoder = bytes_to_unicode()
        self.byte_decoder = {v: k for k, v in self.byte_encoder.items()}
        
        try:
            with gzip.open(self.vocab_path, 'rt', encoding='utf-8') as f:
                merges = f.read().split('\n')
            merges = merges[1:49152-256-2+1]
            merges = [tuple(merge.split()) for merge in merges]
        except Exception as e:
            logger.error(f"Ошибка загрузки словаря: {e}")
            merges = []
            
        vocab = list(bytes_to_unicode().values())
        vocab = vocab + [v + '</w>' for v in vocab]
        for merge in merges:
            vocab.append("".join(merge))
        vocab.extend(['<|startoftext|>', '<|endoftext|>'])
        
        self.encoder = dict(zip(vocab, range(len(vocab))))
        self.decoder = {v: k for k, v in self.encoder.items()}
        self.bpe_ranks = dict(zip(merges, range(len(merges))))
        self.cache = {'<|startoftext|>': '<|startoftext|>', '<|endoftext|>': '<|endoftext|>'}
        
        import regex as re
        self.pat = re.compile(r"""<\|startoftext\|>|<\|endoftext\|>|'s|'t|'re|'ve|'m|'ll|'d|[\p{L}]+|[\p{N}]+|[^\s\p{L}\p{N}]+""", re.IGNORECASE)

    def bpe(self, token):
        if token in self.cache:
            return self.cache[token]
        word = tuple(token[:-1]) + (token[-1] + '</w>',)
        pairs = get_pairs(word)

        if not pairs:
            return token + '</w>'

        while True:
            bigram = min(pairs, key=lambda pair: self.bpe_ranks.get(pair, float('inf')))
            if bigram not in self.bpe_ranks:
                break
            first, second = bigram
            new_word = []
            i = 0
            while i < len(word):
                try:
                    j = word.index(first, i)
                    new_word.extend(word[i:j])
                    i = j
                except ValueError:
                    new_word.extend(word[i:])
                    break

                if word[i] == first and i < len(word)-1 and word[i+1] == second:
                    new_word.append(first + second)
                    i += 2
                else:
                    new_word.append(word[i])
                    i += 1
            word = tuple(new_word)
            if len(word) == 1:
                break
            else:
                pairs = get_pairs(word)
        word = " ".join(word)
        self.cache[token] = word
        return word

    def encode(self, text):
        bpe_tokens = []
        text = html.unescape(html.unescape(text.strip()))
        text = " ".join(text.split())
        for token in re.findall(self.pat, text.lower()):
            token = "".join(self.byte_encoder[b] for b in token.encode('utf-8'))
            bpe_tokens.extend(self.encoder[bpe_token] for bpe_token in self.bpe(token).split(' '))
        return [self.encoder['<|startoftext|>']] + bpe_tokens + [self.encoder['<|endoftext|>']]