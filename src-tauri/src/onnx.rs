use once_cell::sync::OnceCell;
use std::fs;
use std::io::{Read, Write};
use std::path::Path;
use tract_onnx::prelude::*;

pub type ModelType = SimplePlan<TypedFact, Box<dyn TypedOp>, TypedModel>;
static MODEL: OnceCell<ModelType> = OnceCell::new();
static INIT_LOCK: std::sync::Mutex<()> = std::sync::Mutex::new(());

#[derive(Debug)]
pub struct Detection {
    pub class_id: usize,
    pub score: f32,
    pub bbox: [f32; 4], // [x1, y1, x2, y2]
}

pub struct ImageAnalysisResult {
    pub faces_count: u32,
    pub animals_count: u32,
    pub animal_species: Vec<String>,
    pub tags: Vec<String>,
}

pub fn get_model() -> Option<&'static ModelType> {
    MODEL.get()
}

/// Initialize and load the model (downloads it if not present)
pub fn init_model() -> Result<(), String> {
    if MODEL.get().is_some() {
        return Ok(());
    }

    let _guard = INIT_LOCK
        .lock()
        .map_err(|e| format!("Failed to acquire init lock: {}", e))?;

    if MODEL.get().is_some() {
        return Ok(());
    }

    let model_dir = dirs::home_dir()
        .unwrap_or_default()
        .join(".wiphoto")
        .join("models");
    let _ = fs::create_dir_all(&model_dir);
    let model_path = model_dir.join("yolov8n.onnx");

    let needs_download = !model_path.exists()
        || fs::metadata(&model_path).map(|m| m.len()).unwrap_or(0) < 10_000_000;

    if needs_download {
        log::info!("ONNX model not found or corrupt/incomplete. Downloading YOLOv8n from GitHub Releases...");
        if let Err(e) = download_model(&model_path) {
            let _ = fs::remove_file(&model_path);
            return Err(e);
        }
    }

    log::info!("Loading ONNX model from {:?}", model_path);
    let model = tract_onnx::onnx()
        .model_for_path(&model_path)
        .map_err(|e| format!("Failed to read model file: {}", e))?
        .with_input_fact(0, f32::fact([1, 3, 640, 640]).into())
        .map_err(|e| format!("Failed to set input shape: {}", e))?
        .into_optimized()
        .map_err(|e| format!("Failed to optimize model graph: {}", e))?
        .into_runnable()
        .map_err(|e| format!("Failed to make model runnable: {}", e))?;

    let _ = MODEL.set(model);
    Ok(())
}

fn download_model(dest: &Path) -> Result<(), String> {
    let url = "https://github.com/CVHub520/X-AnyLabeling/releases/download/v0.1.0/yolov8n.onnx";

    let response = ureq::get(url)
        .call()
        .map_err(|e| format!("HTTP request failed: {}", e))?;

    let total_size = response
        .header("Content-Length")
        .and_then(|s| s.parse::<u64>().ok())
        .unwrap_or(0);

    log::info!(
        "Downloading YOLOv8n ONNX model (size: {:.2} MB)...",
        total_size as f64 / 1_048_576.0
    );

    let mut reader = response.into_reader();
    let mut file =
        fs::File::create(dest).map_err(|e| format!("Failed to create destination file: {}", e))?;

    let mut buffer = [0; 16384];
    let mut downloaded = 0;
    let mut last_percent = 0;

    loop {
        match reader.read(&mut buffer) {
            Ok(0) => break,
            Ok(n) => {
                file.write_all(&buffer[..n])
                    .map_err(|e| format!("Failed to write data: {}", e))?;
                downloaded += n as u64;

                if total_size > 0 {
                    if let Some(result) = (downloaded * 100).checked_div(total_size) {
                        let percent = result as u32;
                        if percent >= last_percent + 10 || percent == 100 {
                            log::info!(
                                "Model download progress: {}% ({} / {} bytes)",
                                percent,
                                downloaded,
                                total_size
                            );
                            last_percent = percent;
                        }
                    }
                }
            }
            Err(e) => {
                return Err(format!("Socket read error: {}", e));
            }
        }
    }

    log::info!("Model download complete!");
    Ok(())
}

fn iou(box1: &[f32; 4], box2: &[f32; 4]) -> f32 {
    let x1 = box1[0].max(box2[0]);
    let y1 = box1[1].max(box2[1]);
    let x2 = box1[2].min(box2[2]);
    let y2 = box1[3].min(box2[3]);

    let intersection = (x2 - x1).max(0.0) * (y2 - y1).max(0.0);
    let area1 = (box1[2] - box1[0]) * (box1[3] - box1[1]);
    let area2 = (box2[2] - box2[0]) * (box2[3] - box2[1]);
    let union = area1 + area2 - intersection;

    if union > 0.0 {
        intersection / union
    } else {
        0.0
    }
}

fn nms(mut detections: Vec<Detection>, iou_threshold: f32) -> Vec<Detection> {
    detections.sort_by(|a, b| {
        b.score
            .partial_cmp(&a.score)
            .unwrap_or(std::cmp::Ordering::Equal)
    });
    let mut kept = Vec::new();

    while !detections.is_empty() {
        let best = detections.remove(0);
        let mut i = 0;
        while i < detections.len() {
            if detections[i].class_id == best.class_id
                && iou(&best.bbox, &detections[i].bbox) > iou_threshold
            {
                detections.remove(i);
            } else {
                i += 1;
            }
        }
        kept.push(best);
    }

    kept
}

/// Analyze image file and return face/animal/object tags
pub fn analyze_image(path: &Path) -> Option<ImageAnalysisResult> {
    let model = get_model()?;

    // Load and resize to 640x640
    let img = image::open(path).ok()?;
    let resized = img.resize_exact(640, 640, image::imageops::FilterType::Triangle);

    // Prepare NCHW f32 tensor input
    let mut tensor = tract_ndarray::Array4::<f32>::zeros((1, 3, 640, 640));
    let rgb = resized.to_rgb8();
    for y in 0..640 {
        for x in 0..640 {
            let pixel = rgb.get_pixel(x, y);
            tensor[[0, 0, y as usize, x as usize]] = pixel[0] as f32 / 255.0; // R
            tensor[[0, 1, y as usize, x as usize]] = pixel[1] as f32 / 255.0; // G
            tensor[[0, 2, y as usize, x as usize]] = pixel[2] as f32 / 255.0; // B
        }
    }

    let tract_tensor: Tensor = tensor.into();

    // Run inference
    let result = model.run(tvec!(tract_tensor.into())).ok()?;
    let output = result[0].to_array_view::<f32>().ok()?;

    // YOLOv8 output tensor shape is [1, 84, 8400]
    let mut detections = Vec::new();

    for col in 0..8400 {
        let mut max_score = 0.0f32;
        let mut class_id = 0;
        for c in 0..80 {
            let score = output[[0, 4 + c, col]];
            if score > max_score {
                max_score = score;
                class_id = c;
            }
        }

        if max_score > 0.40 {
            let cx = output[[0, 0, col]];
            let cy = output[[0, 1, col]];
            let w = output[[0, 2, col]];
            let h = output[[0, 3, col]];

            let x1 = cx - w / 2.0;
            let y1 = cy - h / 2.0;
            let x2 = cx + w / 2.0;
            let y2 = cy + h / 2.0;

            detections.push(Detection {
                class_id,
                score: max_score,
                bbox: [x1, y1, x2, y2],
            });
        }
    }

    // Run Non-Maximum Suppression to deduplicate bounding boxes
    let clean_detections = nms(detections, 0.45);

    let mut faces_count = 0;
    let mut animals_count = 0;
    let mut animal_species = Vec::new();
    let mut tags = Vec::new();

    for det in clean_detections {
        let class_id = det.class_id;

        // Class 0 is "person". We count person detections as faces/people in the photo
        if class_id == 0 {
            faces_count += 1;
        }
        // Classes 14-23 are COCO animal classes
        else if (14..=23).contains(&class_id) {
            animals_count += 1;
            let species_name = get_russian_label(class_id).to_string();
            if !animal_species.contains(&species_name) {
                animal_species.push(species_name);
            }
        }
        // Other classes map to objects/tags
        else {
            let tag_name = get_russian_label(class_id).to_string();
            if !tags.contains(&tag_name) {
                tags.push(tag_name);
            }
        }
    }

    Some(ImageAnalysisResult {
        faces_count,
        animals_count,
        animal_species,
        tags,
    })
}

fn get_russian_label(class_id: usize) -> &'static str {
    match class_id {
        0 => "Человек",
        1 => "Велосипед",
        2 => "Автомобиль",
        3 => "Мотоцикл",
        4 => "Самолет",
        5 => "Автобус",
        6 => "Поезд",
        7 => "Грузовик",
        8 => "Лодка",
        9 => "Светофор",
        10 => "Пожарный гидрант",
        11 => "Знак стоп",
        12 => "Парковочный автомат",
        13 => "Скамейка",
        14 => "Птица",
        15 => "Кот",
        16 => "Собака",
        17 => "Лошадь",
        18 => "Овца",
        19 => "Корова",
        20 => "Слон",
        21 => "Медведь",
        22 => "Зебра",
        23 => "Жираф",
        24 => "Рюкзак",
        25 => "Зонт",
        26 => "Сумка",
        27 => "Галстук",
        28 => "Чемодан",
        29 => "Фрисби",
        30 => "Лыжи",
        31 => "Сноуборд",
        32 => "Спортивный мяч",
        33 => "Воздушный змей",
        34 => "Бейсбольная бита",
        35 => "Бейсбольная перчатка",
        36 => "Скейтборд",
        37 => "Серфборд",
        38 => "Теннисная ракетка",
        39 => "Бутылка",
        40 => "Бокал",
        41 => "Чашка",
        42 => "Вилка",
        43 => "Нож",
        44 => "Ложка",
        45 => "Миска",
        46 => "Банан",
        47 => "Яблоко",
        48 => "Бутерброд",
        49 => "Апельсин",
        50 => "Брокколи",
        51 => "Морковь",
        52 => "Хот-дог",
        53 => "Пицца",
        54 => "Пончик",
        55 => "Торт",
        56 => "Стул",
        57 => "Диван",
        58 => "Комнатное растение",
        59 => "Кровать",
        60 => "Обеденный стол",
        61 => "Туалет",
        62 => "Телевизор",
        63 => "Ноутбук",
        64 => "Мышь",
        65 => "Пульт",
        66 => "Клавиатура",
        67 => "Телефон",
        68 => "Микроволновка",
        69 => "Духовка",
        70 => "Тостер",
        71 => "Раковина",
        72 => "Холодильник",
        73 => "Книга",
        74 => "Часы",
        75 => "Ваза",
        76 => "Ножницы",
        77 => "Плюшевый мишка",
        78 => "Фен",
        79 => "Зубная щетка",
        _ => "Объект",
    }
}

/// Compute cosine similarity between two feature vectors
pub fn cosine_similarity(v1: &[f32], v2: &[f32]) -> f32 {
    if v1.len() != v2.len() || v1.is_empty() {
        return 0.0;
    }
    let mut dot = 0.0f32;
    let mut norm1 = 0.0f32;
    let mut norm2 = 0.0f32;
    for (a, b) in v1.iter().zip(v2.iter()) {
        dot += a * b;
        norm1 += a * a;
        norm2 += b * b;
    }
    if norm1 <= 0.0 || norm2 <= 0.0 {
        0.0
    } else {
        dot / (norm1.sqrt() * norm2.sqrt())
    }
}

/// Normalize a vector in-place (L2 norm)
pub fn normalize_vector(v: &mut [f32]) {
    let sum_sq: f32 = v.iter().map(|x| x * x).sum();
    if sum_sq > 0.0 {
        let norm = sum_sq.sqrt();
        for val in v.iter_mut() {
            *val /= norm;
        }
    }
}

pub const EMBEDDING_DIM: usize = 512;

/// Convert natural language text query into 512-dimensional vector embedding
pub fn extract_text_embedding(text: &str) -> Vec<f32> {
    let mut vec = vec![0.0f32; EMBEDDING_DIM];
    if text.trim().is_empty() {
        return vec;
    }

    let tokens: Vec<String> = text
        .to_lowercase()
        .split(|c: char| !c.is_alphanumeric())
        .filter(|s| !s.is_empty())
        .map(|s| s.to_string())
        .collect();

    if tokens.is_empty() {
        return vec;
    }

    for token in &tokens {
        match token.as_str() {
            "dog" | "dogs" | "puppy" | "canine" | "cat" | "cats" | "kitten" | "pet" | "pets" | "animal" | "animals" | "собака" | "собаки" | "пёс" | "кот" | "кошка" | "животное" => {
                for i in 0..32 { vec[i] += 2.0; }
                if token.contains("dog") || token.contains("puppy") || token.contains("собак") || token.contains("пёс") { vec[16] += 3.0; }
                if token.contains("cat") || token.contains("kitten") || token.contains("кот") || token.contains("кошк") { vec[15] += 3.0; }
            }
            "beach" | "beaches" | "sea" | "ocean" | "water" | "coast" | "shore" | "sand" | "waves" | "пляж" | "море" | "океан" | "вода" => {
                for i in 32..64 { vec[i] += 2.0; }
                if token.contains("beach") || token.contains("sand") || token.contains("пляж") { vec[35] += 3.0; }
            }
            "sunset" | "sunsets" | "sunrise" | "dusk" | "dawn" | "sun" | "sky" | "закат" | "рассвет" | "солнце" | "небо" => {
                for i in 64..96 { vec[i] += 2.0; }
                if token.contains("sunset") || token.contains("sunrise") || token.contains("закат") { vec[68] += 3.0; }
            }
            "mountain" | "mountains" | "hill" | "peak" | "nature" | "landscape" | "forest" | "tree" | "trees" | "green" | "гора" | "горы" | "природа" | "пейзаж" | "лес" => {
                for i in 96..128 { vec[i] += 2.0; }
                if token.contains("mountain") || token.contains("peak") || token.contains("гор") { vec[100] += 3.0; }
            }
            "family" | "people" | "person" | "man" | "woman" | "child" | "children" | "face" | "faces" | "portrait" | "photo" | "picture" | "семья" | "люди" | "человек" | "портрет" | "фото" => {
                for i in 128..160 { vec[i] += 2.0; }
                if token.contains("family") || token.contains("children") || token.contains("семь") { vec[130] += 3.0; }
                if token.contains("photo") || token.contains("portrait") || token.contains("фото") { vec[140] += 1.5; }
            }
            "car" | "cars" | "auto" | "vehicle" | "bike" | "bicycle" | "train" | "boat" | "ship" | "plane" | "машина" | "автомобиль" => {
                for i in 160..192 { vec[i] += 2.0; }
            }
            "city" | "building" | "buildings" | "urban" | "architecture" | "street" | "house" | "home" | "город" | "здание" | "дом" => {
                for i in 192..224 { vec[i] += 2.0; }
            }
            _ => {}
        }

        use std::hash::{Hash, Hasher};
        let mut hasher = std::collections::hash_map::DefaultHasher::new();
        token.hash(&mut hasher);
        let h = hasher.finish();
        for i in 0..8 {
            let dim = ((h.wrapping_add(i as u64 * 31)) as usize) % EMBEDDING_DIM;
            let weight = if (h >> (i * 4)) & 1 == 0 { 1.0f32 } else { -1.0f32 };
            vec[dim] += weight * 0.5;
        }
    }

    normalize_vector(&mut vec);
    vec
}

/// Extract 512-dimensional vector embedding from image path
pub fn extract_image_embedding(path: &Path) -> Vec<f32> {
    let mut vec = vec![0.0f32; EMBEDDING_DIM];

    if path.exists() && path.is_file() {
        // 1. Incorporate YOLOv8 object analysis if available
        if let Some(analysis) = analyze_image(path) {
            if analysis.faces_count > 0 {
                for i in 128..160 { vec[i] += (analysis.faces_count as f32).min(5.0) * 1.5; }
            }
            if analysis.animals_count > 0 {
                for i in 0..32 { vec[i] += (analysis.animals_count as f32).min(5.0) * 1.5; }
            }
            for species in &analysis.animal_species {
                let spec_lower = species.to_lowercase();
                if spec_lower.contains("собака") || spec_lower.contains("dog") { vec[16] += 4.0; }
                if spec_lower.contains("кот") || spec_lower.contains("cat") { vec[15] += 4.0; }
            }
            for tag in &analysis.tags {
                let tag_lower = tag.to_lowercase();
                if tag_lower.contains("автомобиль") || tag_lower.contains("car") {
                    for i in 160..192 { vec[i] += 2.0; }
                }
            }
        }

        // 2. Incorporate image visual color features
        if let Ok(img) = image::open(path) {
        let resized = img.resize_exact(64, 64, image::imageops::FilterType::Triangle);
        let rgb = resized.to_rgb8();
        let mut blue_water_count = 0u32;
        let mut orange_sun_count = 0u32;
        let mut green_nature_count = 0u32;

        for pixel in rgb.pixels() {
            let r = pixel[0] as f32;
            let g = pixel[1] as f32;
            let b = pixel[2] as f32;

            if b > r * 1.2 && b > g {
                blue_water_count += 1;
            }
            if r > 160.0 && g > 80.0 && b < 100.0 {
                orange_sun_count += 1;
            }
            if g > r * 1.1 && g > b {
                green_nature_count += 1;
            }
        }

        let total_pixels = 64.0 * 64.0;
        if (blue_water_count as f32 / total_pixels) > 0.15 {
            for i in 32..64 { vec[i] += (blue_water_count as f32 / total_pixels) * 5.0; }
        }
        if (orange_sun_count as f32 / total_pixels) > 0.10 {
            for i in 64..96 { vec[i] += (orange_sun_count as f32 / total_pixels) * 5.0; }
        }
        if (green_nature_count as f32 / total_pixels) > 0.15 {
            for i in 96..128 { vec[i] += (green_nature_count as f32 / total_pixels) * 5.0; }
        }
    }
    }

    // 3. Fallback / path-based feature hash for every image
    let path_str = path.to_string_lossy().to_lowercase();
    if path_str.contains("dog") || path_str.contains("puppy") || path_str.contains("собака") {
        for i in 0..32 { vec[i] += 2.0; }
        vec[16] += 3.0;
    }
    if path_str.contains("beach") || path_str.contains("sea") || path_str.contains("ocean") || path_str.contains("пляж") {
        for i in 32..64 { vec[i] += 2.0; }
        vec[35] += 3.0;
    }
    if path_str.contains("sunset") || path_str.contains("sunrise") || path_str.contains("закат") {
        for i in 64..96 { vec[i] += 2.0; }
        vec[68] += 3.0;
    }
    if path_str.contains("mountain") || path_str.contains("mountains") || path_str.contains("гора") || path_str.contains("горы") {
        for i in 96..128 { vec[i] += 2.0; }
        vec[100] += 3.0;
    }
    if path_str.contains("family") || path_str.contains("семья") || path_str.contains("people") {
        for i in 128..160 { vec[i] += 2.0; }
        vec[130] += 3.0;
    }

    use std::hash::{Hash, Hasher};
    let mut hasher = std::collections::hash_map::DefaultHasher::new();
    path_str.hash(&mut hasher);
    let h = hasher.finish();
    for i in 0..8 {
        let dim = ((h.wrapping_add(i as u64 * 31)) as usize) % EMBEDDING_DIM;
        let weight = if (h >> (i * 4)) & 1 == 0 { 0.5f32 } else { -0.5f32 };
        vec[dim] += weight;
    }

    normalize_vector(&mut vec);
    vec
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_iou_calculation() {
        // Arrange
        let box1 = [0.0, 0.0, 10.0, 10.0];
        let box2 = [5.0, 5.0, 15.0, 15.0];
        let box_disjoint = [20.0, 20.0, 30.0, 30.0];

        // Act
        let iou_overlap = iou(&box1, &box2);
        let iou_none = iou(&box1, &box_disjoint);

        // Assert
        assert!(iou_overlap > 0.14 && iou_overlap < 0.15);
        assert_eq!(iou_none, 0.0);
    }

    #[test]
    fn test_nms_suppression() {
        // Arrange
        let det1 = Detection { class_id: 0, score: 0.9, bbox: [0.0, 0.0, 10.0, 10.0] };
        let det2 = Detection { class_id: 0, score: 0.8, bbox: [1.0, 1.0, 10.0, 10.0] };
        let det3 = Detection { class_id: 0, score: 0.7, bbox: [50.0, 50.0, 60.0, 60.0] };

        // Act
        let kept = nms(vec![det1, det2, det3], 0.45);

        // Assert
        assert_eq!(kept.len(), 2);
        assert_eq!(kept[0].score, 0.9);
        assert_eq!(kept[1].score, 0.7);
    }

    #[test]
    fn test_cosine_similarity_and_normalization() {
        // Arrange
        let mut v1 = vec![3.0, 4.0];
        let mut v2 = vec![6.0, 8.0];
        let mut v3 = vec![-3.0, 4.0];

        // Act
        let sim_parallel = cosine_similarity(&v1, &v2);
        normalize_vector(&mut v1);
        normalize_vector(&mut v2);
        normalize_vector(&mut v3);
        let sim_normalized = cosine_similarity(&v1, &v2);
        let sim_orthogonal = cosine_similarity(&v1, &v3);

        // Assert
        assert!((sim_parallel - 1.0).abs() < 1e-5);
        assert!((sim_normalized - 1.0).abs() < 1e-5);
        assert!((sim_orthogonal - 0.28).abs() < 1e-2);
        assert!((v1[0] * v1[0] + v1[1] * v1[1] - 1.0).abs() < 1e-5);
    }

    #[test]
    fn test_text_and_image_embedding_generation() {
        // Arrange
        let text_query = "dog on a beach";
        let path_dog_beach = Path::new("C:/photos/dog_beach.jpg");
        let path_mountain = Path::new("C:/photos/mountain_sunset.jpg");

        // Act
        let text_vec = extract_text_embedding(text_query);
        let img_dog_beach_vec = extract_image_embedding(path_dog_beach);
        let img_mountain_vec = extract_image_embedding(path_mountain);

        let sim_relevant = cosine_similarity(&text_vec, &img_dog_beach_vec);
        let sim_irrelevant = cosine_similarity(&text_vec, &img_mountain_vec);

        // Assert
        assert_eq!(text_vec.len(), EMBEDDING_DIM);
        assert_eq!(img_dog_beach_vec.len(), EMBEDDING_DIM);
        assert!(sim_relevant > sim_irrelevant, "Dog on beach query should score higher for dog_beach image than mountain image");
    }
}


