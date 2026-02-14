import hashlib
import os

def get_file_hash(file_path):
    """Вычисляет MD5 хеш файла."""
    hasher = hashlib.md5()
    with open(file_path, 'rb') as f:
        buf = f.read()
        hasher.update(buf)
    return hasher.hexdigest()

def find_duplicates(train_path, val_path):
    train_hashes = {}
    duplicates = []

    # Собираем хеши из папки train
    for img in os.listdir(train_path):
        if img.lower().endswith(('.png', '.jpg', '.jpeg')):
            full_path = os.path.join(train_path, img)
            train_hashes[get_file_hash(full_path)] = img

    # Проверяем папку val
    for img in os.listdir(val_path):
        if img.lower().endswith(('.png', '.jpg', '.jpeg')):
            full_path = os.path.join(val_path, img)
            img_hash = get_file_hash(full_path)
            
            if img_hash in train_hashes:
                duplicates.append((img, train_hashes[img_hash]))

    return duplicates

# Укажите ваши пути к папкам images
train_dir = "data/train/images"
val_dir = "data/valid/images"

dupes = find_duplicates(train_dir, val_dir)

if dupes:
    print(f"❌ Найдено дубликатов: {len(dupes)}")
    for val_img, train_img in dupes:
        print(f"Файл {val_img} (val) совпадает с {train_img} (train)")
else:
    print("✅ Дубликатов между train и val не обнаружено.")