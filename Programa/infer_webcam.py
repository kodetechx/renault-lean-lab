"""
infer_webcam.py

Roda o modelo treinado ao vivo, a partir da webcam, simulando o
funcionamento de uma estacao. Classifica cada frame, compara com a camada
esperada para a estacao configurada, e:

  - dispara um alerta em tela quando a camada detectada nao bate com a
    esperada (atende ao requisito "automacao de processos" do documento
    oficial da demanda);
  - registra eventos (contagem + tempo de ciclo) em um arquivo CSV local,
    servindo de stub para a futura integracao com a API/backend (Fase 1.2).

Uso:
    python infer_webcam.py --model modelo_camada.keras --class_names class_names.json \
        --estacao camada_verde --camera 0

Pressione "q" para encerrar.
"""
import argparse
import csv
import json
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import tensorflow as tf

CONFIDENCE_THRESHOLD = 0.75      # confianca minima para considerar a predicao valida
CONSECUTIVE_FRAMES_NEEDED = 5    # n. de frames seguidos com a mesma classe para confirmar (evita ruido)
COOLDOWN_SECONDS = 3.0           # tempo minimo entre duas contagens (evita contar 2x a mesma peca)


def preprocess(frame, img_size):
    # O modelo salvo ja inclui a camada de preprocess_input do MobileNetV2
    # (ver build_model() em train_classifier.py), entao aqui so redimensionamos
    # e convertemos para RGB, sem normalizar de novo.
    img = cv2.resize(frame, (img_size, img_size))
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    return np.expand_dims(img.astype("float32"), axis=0)


def log_event(csv_path, estacao, classe_detectada, status, ciclo_segundos):
    """
    Stub de integracao: hoje grava em CSV local; na Fase 1.2 este mesmo ponto
    deve ser trocado por uma chamada a API do backend (ex.: requests.post ou
    publicacao MQTT), sem precisar mudar o resto da logica de inferencia.
    """
    novo_arquivo = not csv_path.exists()
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if novo_arquivo:
            writer.writerow(["timestamp", "estacao", "classe_detectada", "status", "tempo_ciclo_s"])
        writer.writerow([datetime.now().isoformat(), estacao, classe_detectada, status, f"{ciclo_segundos:.2f}"])


def main():
    parser = argparse.ArgumentParser(description="Inferencia ao vivo via webcam")
    parser.add_argument("--model", required=True)
    parser.add_argument("--class_names", required=True)
    parser.add_argument(
        "--estacao", required=True, help="Nome da classe esperada para esta estacao, ex.: camada_verde"
    )
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--img_size", type=int, default=224)
    parser.add_argument("--log_file", default="eventos.csv")
    args = parser.parse_args()

    model = tf.keras.models.load_model(args.model)
    with open(args.class_names, "r", encoding="utf-8") as f:
        class_names = json.load(f)

    if args.estacao not in class_names:
        raise SystemExit(f"'{args.estacao}' nao e uma classe conhecida. Classes disponiveis: {class_names}")

    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        raise SystemExit("Nao foi possivel abrir a webcam. Verifique o indice em --camera.")

    csv_path = Path(args.log_file)

    consecutive_count = 0
    last_stable_class = None
    last_count_time = 0.0
    ciclo_inicio = time.time()

    print("Pressione 'q' para sair.")
    while True:
        ok, frame = cap.read()
        if not ok:
            print("Falha ao ler frame da webcam.")
            break

        input_tensor = preprocess(frame, args.img_size)
        probs = model.predict(input_tensor, verbose=0)[0]
        pred_idx = int(np.argmax(probs))
        pred_class = class_names[pred_idx]
        pred_conf = float(probs[pred_idx])

        # Estabilizacao: so considera a predicao "confirmada" depois de N
        # frames seguidos com a mesma classe e confianca suficiente.
        if pred_conf >= CONFIDENCE_THRESHOLD and pred_class == last_stable_class:
            consecutive_count += 1
        else:
            consecutive_count = 1
            last_stable_class = pred_class

        confirmado = consecutive_count >= CONSECUTIVE_FRAMES_NEEDED
        agora = time.time()

        status_texto = f"{pred_class} ({pred_conf:.0%})"
        cor = (0, 255, 0)

        if confirmado and (agora - last_count_time) > COOLDOWN_SECONDS:
            tempo_ciclo = agora - ciclo_inicio
            if pred_class == args.estacao:
                log_event(csv_path, args.estacao, pred_class, "OK", tempo_ciclo)
                status_texto = f"OK: {pred_class}"
                cor = (0, 200, 0)
            else:
                log_event(csv_path, args.estacao, pred_class, "ALERTA_CAMADA_INCORRETA", tempo_ciclo)
                status_texto = f"ALERTA: esperado {args.estacao}, veio {pred_class}"
                cor = (0, 0, 255)
                print(
                    f"[ALERTA] Estacao '{args.estacao}' recebeu camada '{pred_class}' "
                    f"as {datetime.now().strftime('%H:%M:%S')}"
                )

            last_count_time = agora
            ciclo_inicio = agora  # reinicia a contagem de tempo de ciclo para a proxima peca

        cv2.putText(frame, status_texto, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, cor, 2)
        cv2.putText(
            frame, f"Estacao esperada: {args.estacao}", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1
        )
        cv2.imshow("Estacao - MVP Lean Lab", frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()
    print(f"\nEventos registrados em: {csv_path.resolve()}")


if __name__ == "__main__":
    main()
