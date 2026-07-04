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

    let _guard = INIT_LOCK.lock().map_err(|e| format!("Failed to acquire init lock: {}", e))?;

    if MODEL.get().is_some() {
        return Ok(());
    }

    let model_dir = dirs::home_dir()
        .unwrap_or_default()
        .join(".wiphoto")
        .join("models");
    let _ = fs::create_dir_all(&model_dir);
    let model_path = model_dir.join("yolov8n.onnx");

    let needs_download = !model_path.exists() || fs::metadata(&model_path).map(|m| m.len()).unwrap_or(0) < 10_000_000;

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
        .with_input_fact(0, f32::fact(&[1, 3, 640, 640]).into())
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

    log::info!("Downloading YOLOv8n ONNX model (size: {:.2} MB)...", total_size as f64 / 1_048_576.0);

    let mut reader = response.into_reader();
    let mut file = fs::File::create(dest)
        .map_err(|e| format!("Failed to create destination file: {}", e))?;

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
                    let percent = (downloaded * 100 / total_size) as u32;
                    if percent >= last_percent + 10 || percent == 100 {
                        log::info!("Model download progress: {}% ({} / {} bytes)", percent, downloaded, total_size);
                        last_percent = percent;
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
    detections.sort_by(|a, b| b.score.partial_cmp(&a.score).unwrap_or(std::cmp::Ordering::Equal));
    let mut kept = Vec::new();

    while !detections.is_empty() {
        let best = detections.remove(0);
        let mut i = 0;
        while i < detections.len() {
            if detections[i].class_id == best.class_id && iou(&best.bbox, &detections[i].bbox) > iou_threshold {
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
        else if class_id >= 14 && class_id <= 23 {
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
