"""
infer_webcam.py

Roda o modelo treinado ao vivo, a partir da webcam, simulando o
funcionamento de uma estacao. Classifica cada frame e usa uma maquina de
estados simples (vazio -> peca presente -> vazio -> ...) para:

  - contar uma peca apenas na TRANSICAO de "vazio" para "peca detectada"
    (evita contar varias vezes a mesma peca parada em frente a camera);
  - disparar um alerta em tela quando a camada detectada nao bate com a
    esperada (atende ao requisito "automacao de processos" do documento
    oficial da demanda);
  - enviar os eventos para a API do backend, com fallback em CSV local se a
    API estiver inacessivel (ex.: instabilidade do hotspot).

Requer que o dataset/modelo tenha uma classe "vazio" (bancada sem peca) —
ver README para o passo a passo de captura e treino dessa classe.

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
import requests
import tensorflow as tf

CONFIDENCE_THRESHOLD = 0.75      # confianca minima para considerar a predicao valida
CONSECUTIVE_FRAMES_NEEDED = 5    # n. de frames seguidos com a mesma classe para confirmar (evita ruido)
VAZIO_CLASS_NAME = "vazio"       # nome da classe que representa "bancada sem peca"


def preprocess(frame, img_size):
    # O modelo (ver train_classifier.py) ja tem a camada preprocess_input
    # embutida no grafo salvo; aplica-la aqui de novo faria o pre-processamento
    # em dobro e jogaria a imagem para fora da distribuicao vista no treino.
    img = cv2.resize(frame, (img_size, img_size))
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    return np.expand_dims(img.astype("float32"), axis=0)


def log_event(api_url, csv_backup_path, estacao, classe_detectada, status, ciclo_segundos):
    """
    Envia o evento para a API do backend. Se a API estiver inacessivel no
    momento (ex.: instabilidade do hotspot usado como rede do prototipo), o
    evento nao e perdido: cai em um CSV de backup local, que pode ser
    reenviado manualmente depois.
    """
    payload = {
        "estacao": estacao,
        "classe_detectada": classe_detectada,
        "status": status,
        "tempo_ciclo_s": ciclo_segundos,
    }
    try:
        resp = requests.post(f"{api_url}/eventos", json=payload, timeout=2)
        resp.raise_for_status()
        return
    except requests.exceptions.RequestException as e:
        print(f"[AVISO] Nao foi possivel enviar o evento para a API ({e}). Salvando em backup local.")

    novo_arquivo = not csv_backup_path.exists()
    with open(csv_backup_path, "a", newline="", encoding="utf-8") as f:
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
    parser.add_argument("--api_url", default="http://localhost:8000", help="URL base da API do backend")
    parser.add_argument(
        "--backup_file", default="eventos_backup.csv", help="CSV usado apenas se a API estiver inacessivel"
    )
    args = parser.parse_args()

    model = tf.keras.models.load_model(args.model)
    with open(args.class_names, "r", encoding="utf-8") as f:
        class_names = json.load(f)

    if args.estacao not in class_names:
        raise SystemExit(f"'{args.estacao}' nao e uma classe conhecida. Classes disponiveis: {class_names}")

    if VAZIO_CLASS_NAME not in class_names:
        print(
            f"[AVISO] Classe '{VAZIO_CLASS_NAME}' nao encontrada em class_names.json. "
            "A contagem vai continuar usando o modo antigo (sem deteccao de presenca) "
            "ate que o modelo seja retreinado com essa classe."
        )

    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        raise SystemExit("Nao foi possivel abrir a webcam. Verifique o indice em --camera.")

    csv_path = Path(args.backup_file)

    # --- Maquina de estados de presenca ---
    # AGUARDANDO_PECA: bancada vazia (ou inicio do programa) -> a proxima
    #                  classe "nao vazia" confirmada conta como peca nova.
    # PECA_PRESENTE:   ja contamos essa peca -> so volta a contar quando
    #                  o sistema confirmar "vazio" de novo.
    estado = "AGUARDANDO_PECA"

    consecutive_count = 0
    last_stable_class = None
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
        classe_confirmada = pred_class if confirmado else None

        status_texto = f"{pred_class} ({pred_conf:.0%})"
        cor = (200, 200, 200)

        if classe_confirmada == VAZIO_CLASS_NAME:
            # Bancada vazia confirmada: libera a proxima contagem.
            estado = "AGUARDANDO_PECA"
            status_texto = "Bancada vazia"
            cor = (180, 180, 180)

        elif classe_confirmada is not None and classe_confirmada != VAZIO_CLASS_NAME:
            if estado == "AGUARDANDO_PECA":
                # Transicao vazio -> peca: e uma peca NOVA, conta agora.
                agora = time.time()
                tempo_ciclo = agora - ciclo_inicio

                if pred_class == args.estacao:
                    log_event(args.api_url, csv_path, args.estacao, pred_class, "OK", tempo_ciclo)
                    status_texto = f"OK: {pred_class}"
                    cor = (0, 200, 0)
                else:
                    log_event(
                        args.api_url, csv_path, args.estacao, pred_class, "ALERTA_CAMADA_INCORRETA", tempo_ciclo
                    )
                    status_texto = f"ALERTA: esperado {args.estacao}, veio {pred_class}"
                    cor = (0, 0, 255)
                    print(
                        f"[ALERTA] Estacao '{args.estacao}' recebeu camada '{pred_class}' "
                        f"as {datetime.now().strftime('%H:%M:%S')}"
                    )

                ciclo_inicio = agora  # reinicia a contagem de tempo de ciclo para a proxima peca
                estado = "PECA_PRESENTE"
            else:
                # PECA_PRESENTE: mesma peca continua ali, nao conta de novo.
                status_texto = f"{pred_class} (ja contada)"
                cor = (0, 150, 200)

        cv2.putText(frame, status_texto, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, cor, 2)
        cv2.putText(
            frame, f"Estacao esperada: {args.estacao}", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1
        )
        cv2.putText(frame, f"Estado: {estado}", (10, 85), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        cv2.imshow("Estacao - MVP Lean Lab", frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()
    print(f"\nEventos enviados para: {args.api_url} (backup local, se usado, em: {csv_path.resolve()})")


if __name__ == "__main__":
    main()