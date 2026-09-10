"""
train_classifier.py

Treina um classificador de camada (base, verde, amarela, azul, vermelha)
usando transfer learning com MobileNetV2 (TensorFlow/Keras).

Uso:
    python train_classifier.py --dataset_dir ./dataset --epochs 15 --img_size 224

Saida:
    - modelo salvo em ./modelo_camada.keras
    - mapeamento de classes salvo em ./class_names.json
    - relatorio de avaliacao impresso no console (usando o conjunto de teste)
"""
import argparse
import json
from pathlib import Path

import numpy as np
import tensorflow as tf
from sklearn.metrics import classification_report, confusion_matrix
from tensorflow.keras import layers, models


def build_model(num_classes, img_size):
    base_model = tf.keras.applications.MobileNetV2(
        input_shape=(img_size, img_size, 3),
        include_top=False,
        weights="imagenet",
    )
    base_model.trainable = False  # transfer learning: comecamos com a base congelada

    data_augmentation = models.Sequential([
        layers.RandomFlip("horizontal"),
        layers.RandomRotation(0.08),
        layers.RandomZoom(0.1),
        layers.RandomBrightness(0.15),
    ])

    inputs = tf.keras.Input(shape=(img_size, img_size, 3))
    x = data_augmentation(inputs)
    x = tf.keras.applications.mobilenet_v2.preprocess_input(x)
    x = base_model(x, training=False)
    x = layers.GlobalAveragePooling2D()(x)
    x = layers.Dropout(0.2)(x)
    outputs = layers.Dense(num_classes, activation="softmax")(x)
    model = tf.keras.Model(inputs, outputs)

    model.compile(
        optimizer=tf.keras.optimizers.Adam(1e-3),
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )
    return model


def main():
    parser = argparse.ArgumentParser(description="Treina o classificador de camada")
    parser.add_argument("--dataset_dir", required=True, help="Pasta com train/val/test")
    parser.add_argument("--img_size", type=int, default=224)
    parser.add_argument("--batch_size", type=int, default=16)
    parser.add_argument("--epochs", type=int, default=15)
    parser.add_argument("--output_model", default="modelo_camada.keras")
    args = parser.parse_args()

    dataset_dir = Path(args.dataset_dir)

    train_ds = tf.keras.utils.image_dataset_from_directory(
        dataset_dir / "train", image_size=(args.img_size, args.img_size), batch_size=args.batch_size
    )
    val_ds = tf.keras.utils.image_dataset_from_directory(
        dataset_dir / "val", image_size=(args.img_size, args.img_size), batch_size=args.batch_size
    )
    test_ds = tf.keras.utils.image_dataset_from_directory(
        dataset_dir / "test",
        image_size=(args.img_size, args.img_size),
        batch_size=args.batch_size,
        shuffle=False,
    )

    class_names = train_ds.class_names
    print("Classes encontradas:", class_names)

    train_ds = train_ds.prefetch(tf.data.AUTOTUNE)
    val_ds = val_ds.prefetch(tf.data.AUTOTUNE)

    model = build_model(num_classes=len(class_names), img_size=args.img_size)
    model.summary()

    callbacks = [
        tf.keras.callbacks.EarlyStopping(patience=4, restore_best_weights=True),
    ]

    model.fit(train_ds, validation_data=val_ds, epochs=args.epochs, callbacks=callbacks)

    model.save(args.output_model)
    with open("class_names.json", "w", encoding="utf-8") as f:
        json.dump(class_names, f, ensure_ascii=False, indent=2)
    print(f"\nModelo salvo em: {args.output_model}")
    print("Mapeamento de classes salvo em: class_names.json")

    # Avaliacao no conjunto de teste (isolado do treino/validacao)
    y_true = np.concatenate([y.numpy() for _, y in test_ds])
    y_pred_probs = model.predict(test_ds)
    y_pred = np.argmax(y_pred_probs, axis=1)

    print("\n=== Relatorio no conjunto de teste ===")
    print(classification_report(y_true, y_pred, target_names=class_names))
    print("Matriz de confusao (linhas = real, colunas = previsto):")
    print(confusion_matrix(y_true, y_pred))


if __name__ == "__main__":
    main()
