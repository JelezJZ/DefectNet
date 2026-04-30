import pandas as pd
import matplotlib.pyplot as plt
import os

file_path = '../runs/detect/pcb_defect_detector_v13/results.csv' 

if not os.path.exists(file_path):
    print(f"Ошибка: Файл '{file_path}' не найден в текущей директории.")
else:
    df = pd.read_csv(file_path)
    
    df.columns = [c.strip() for c in df.columns]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))
    fig.suptitle('Динамика функции потерь и метрик качества', fontsize=14)

    # --- ЛЕВЫЙ ГРАФИК: ПОТЕРИ (Losses) ---
    # Обучение (сплошные линии)
    ax1.plot(df['epoch'], df['train/box_loss'], label='Train Box Loss', color='#1f77b4', lw=1.5)
    ax1.plot(df['epoch'], df['train/cls_loss'], label='Train Cls Loss', color='#ff7f0e', lw=1.5)
    ax1.plot(df['epoch'], df['train/dfl_loss'], label='Train DFL Loss', color='#2ca02c', lw=1.5)

    # Валидация (пунктирные линии)
    ax1.plot(df['epoch'], df['val/box_loss'], label='Val Box Loss', color='#1f77b4', linestyle='--', alpha=0.8)
    ax1.plot(df['epoch'], df['val/cls_loss'], label='Val Cls Loss', color='#ff7f0e', linestyle='--', alpha=0.8)
    ax1.plot(df['epoch'], df['val/dfl_loss'], label='Val DFL Loss', color='#2ca02c', linestyle='--', alpha=0.8)

    ax1.set_title('Функции потерь')
    ax1.set_xlabel('Эпоха')
    ax1.set_ylabel('Loss')
    ax1.legend()
    ax1.grid(True, linestyle=':', alpha=0.6)

    # --- ПРАВЫЙ ГРАФИК: МЕТРИКИ (Metrics) ---
    ax2.plot(df['epoch'], df['metrics/mAP50(B)'], label='mAP@50', color='#d62728', lw=2)
    ax2.plot(df['epoch'], df['metrics/mAP50-95(B)'], label='mAP@50-95', color='#9467bd', lw=2)
    ax2.plot(df['epoch'], df['metrics/precision(B)'], label='Precision', color='#17becf', alpha=0.5)
    ax2.plot(df['epoch'], df['metrics/recall(B)'], label='Recall', color='#e377c2', alpha=0.5)

    ax2.set_title('Метрики качества')
    ax2.set_xlabel('Эпоха')
    ax2.set_ylabel('Value')
    ax2.set_ylim(0, 1)
    ax2.legend(loc='lower right')
    ax2.grid(True, linestyle=':', alpha=0.6)

    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    
    # Сохранение и показ
    plt.savefig('training_results.png', dpi=300)
    plt.show()