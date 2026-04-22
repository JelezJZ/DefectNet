import os
import glob
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from tqdm import tqdm
import cv2
import random
from pathlib import Path

PATH_TO_LABELS = '../datasets/pcb-defects-final/train/labels' 
CLASS_NAMES = ['mouse_bite', 'open_circuit', 'short', 'spur', 'spurious_copper', 'background']

def collect_stats(labels_path):
    data = []
    label_files = glob.glob(os.path.join(labels_path, '*.txt'))
    
    if not label_files:
        print(f"!!! ОШИБКА: Файлы не найдены в {labels_path}")
        return pd.DataFrame(columns=['class_id', 'x', 'y', 'w', 'h'])

    print(f"Обработка {len(label_files)} файлов разметки...")
    for file_path in tqdm(label_files):
        with open(file_path, 'r') as f:
            lines = f.readlines()
            
            if not lines:
                data.append({'class_id': 5, 'x': np.nan, 'y': np.nan, 'w': np.nan, 'h': np.nan})
                continue
                
            for line in lines:
                parts = line.split()
                if len(parts) >= 5:
                    try:
                        c, x, y, w, h = map(float, parts[:5])
                        data.append({'class_id': int(c), 'x': x, 'y': y, 'w': w, 'h': h})
                    except ValueError:
                        continue
    
    return pd.DataFrame(data)

df = collect_stats(PATH_TO_LABELS)

if df.empty:
    print("Датасет пуст. Проверьте путь к labels.")
    df = pd.DataFrame(columns=['class_id', 'x', 'y', 'w', 'h', 'class_name', 'area_pct'])
else:
    df['class_name'] = df['class_id'].apply(lambda x: CLASS_NAMES[x] if x < len(CLASS_NAMES) else 'unknown')
    df['area_pct'] = (df['w'] * df['h']) * 100

plt.style.use('seaborn-v0_8-whitegrid')

# 1. Распределение классов (Рис 4.2)
plt.figure(figsize=(12, 7))

class_counts = df['class_name'].value_counts().reindex(CLASS_NAMES).fillna(0)

ax = sns.barplot(
    x=class_counts.index, 
    y=class_counts.values, 
    hue=class_counts.index, 
    palette='viridis', 
    edgecolor='black',
    legend=False
)

for container in ax.containers:
    ax.bar_label(container, padding=3, fontsize=11, fontweight='bold')

plt.title('Распределение количества экземпляров по классам', fontsize=14, pad=20)
plt.ylabel('Количество экземпляров (шт.)', fontsize=12)
plt.xlabel('Тип дефекта', fontsize=12)
plt.xticks(rotation=15)

plt.ylim(0, class_counts.max() * 1.15) 

plt.grid(axis='y', linestyle='--', alpha=0.7)
plt.tight_layout()

plt.savefig('plot_4_2.png', dpi=300)

# 2. Геометрия BBox (Рис 4.3)
fig, axes = plt.subplots(1, 2, figsize=(15, 6))
sns.boxplot(data=df.dropna(), x='class_name', y='w', ax=axes[0])
axes[0].set_title('Распределение ширины (нормализ.)')
axes[0].tick_params(axis='x', rotation=45)

sns.boxplot(data=df.dropna(), x='class_name', y='h', ax=axes[1])
axes[1].set_title('Распределение высоты (нормализ.)')
axes[1].tick_params(axis='x', rotation=45)
plt.tight_layout()
plt.savefig('plot_4_3.png')

# 3. Тепловая карта (Рис 4.4)
plt.figure(figsize=(8, 7))
clean_df = df.dropna()
heatmap, xedges, yedges = np.histogram2d(clean_df['x'], clean_df['y'], bins=50, range=[[0, 1], [0, 1]])
sns.heatmap(heatmap.T, cmap='magma', cbar_kws={'label': 'Плотность дефектов'})
plt.title('Тепловая карта локализации')
plt.gca().invert_yaxis()
plt.savefig('plot_4_4.png')

# 4. Мозаика (Рис 4.5)

DATASET_PATH = Path('../datasets/pcb-defects-final/train')
IMAGES_DIR = DATASET_PATH / 'images'
LABELS_DIR = DATASET_PATH / 'labels'
CLASS_NAMES = ['mouse_bite', 'open_circuit', 'short', 'spur', 'spurious_copper']

def draw_yolo_boxes(image, label_path, color=(0, 255, 0)):
    h, w, _ = image.shape
    if not os.path.exists(label_path):
        return image
    
    with open(label_path, 'r') as f:
        for line in f:
            cls, x, y, bw, bh = map(float, line.split())
            
            x1 = int((x - bw/2) * w)
            y1 = int((y - bh/2) * h)
            x2 = int((x + bw/2) * w)
            y2 = int((y + bh/2) * h)
            
            cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)
            cv2.putText(image, CLASS_NAMES[int(cls)], (x1, y1-5), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
    return image

class_samples = {i: [] for i in range(len(CLASS_NAMES))}
label_files = list(LABELS_DIR.glob('*.txt'))

for lp in label_files:
    with open(lp, 'r') as f:
        lines = f.readlines()
        if lines:
            first_cls = int(lines[0].split()[0])
            if first_cls < len(CLASS_NAMES):
                class_samples[first_cls].append(lp.stem)

rows = len(CLASS_NAMES)
cols = 3
plt.figure(figsize=(cols * 4, rows * 4))

for cls_id, samples in class_samples.items():
    if len(samples) < cols:
        selected = samples
    else:
        selected = random.sample(samples, cols)
    
    for i, img_name in enumerate(selected):
        img_path = IMAGES_DIR / f"{img_name}.jpg"
        lbl_path = LABELS_DIR / f"{img_name}.txt"
        
        img = cv2.imread(str(img_path))
        if img is None: continue
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img = draw_yolo_boxes(img, lbl_path)
        
        plt.subplot(rows, cols, cls_id * cols + i + 1)
        plt.imshow(img)
        plt.title(f"Class: {CLASS_NAMES[cls_id]}")
        plt.axis('off')

plt.tight_layout()
plt.savefig('plot_4_5.png', dpi=300)

plt.figure(figsize=(10, 8))
# Фильтруем данные
df_plot = df.dropna(subset=['w', 'h'])
df_plot = df_plot[df_plot['class_name'] != 'background']

# Используем прозрачность и уменьшенный размер точек для борьбы с наложением
sns.scatterplot(data=df_plot, x='w', y='h', hue='class_name', 
                palette='viridis', s=20, alpha=0.4, edgecolor=None)

# Диагональ (квадратные объекты)
plt.plot([0, 0.6], [0, 0.6], color='red', linestyle='--', alpha=0.5, label='Aspect Ratio = 1')

plt.title('Распределение размеров дефектов (W vs H)', fontsize=14)
plt.xlabel('Нормализованная ширина', fontsize=12)
plt.ylabel('Нормализованная высота', fontsize=12)
plt.legend(title='Классы', bbox_to_anchor=(1.05, 1), loc='upper left')
plt.grid(True, linestyle=':', alpha=0.6)
plt.tight_layout()
plt.savefig('scatter_sizes.png', dpi=300)

plt.figure(figsize=(12, 6))

# Рисуем распределение ширины для всех классов
sns.kdeplot(data=df_plot, x='w', hue='class_name', palette='viridis', 
            fill=True, common_norm=False, alpha=0.3)

plt.title('Плотность распределения ширины дефектов по классам', fontsize=14)
plt.xlabel('Нормализованная ширина', fontsize=12)
plt.ylabel('Плотность', fontsize=12)
plt.xlim(0, 0.25) # Ограничим для наглядности основной массы
plt.grid(axis='y', alpha=0.3)
plt.tight_layout()
plt.savefig('density_width.png', dpi=300)

# Создаем длинную таблицу для удобства отрисовки (Melt)
df_melted = df_plot.melt(id_vars=['class_name'], value_vars=['w', 'h'], 
                         var_name='Dimension', value_name='Value')

plt.figure(figsize=(14, 7))
sns.boxplot(data=df_melted, x='class_name', y='Value', hue='Dimension', 
            palette='Set2', fliersize=3, width=0.7)

plt.title('Статистический анализ размеров (Box Plot)', fontsize=14)
plt.xlabel('Класс дефекта', fontsize=12)
plt.ylabel('Нормализованное значение', fontsize=12)
plt.xticks(rotation=15)
plt.grid(axis='y', linestyle='--', alpha=0.7)
plt.tight_layout()
plt.savefig('boxplot_stats.png', dpi=300)

print("Графики сохранены в текущую директорию.")