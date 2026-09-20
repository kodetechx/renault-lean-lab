"""
infer_webcam_yolo.py

Roda o modelo YOLO treinado (train_yolo.py) ao vivo, a partir da webcam,
simulando o funcionamento de uma estacao — versao Fase 2 (detecção de
objeto), substituindo o infer_webcam.py da Fase 1 (classificação).

Diferencas principais em relacao ao infer_webcam.py da Fase 1:
  - Detecta MULTIPLAS pecas no mesmo frame (nao um unico rotulo por frame),
    resolvendo a limitacao do MobileNetV2 discutida no planejamento da
    Fase 2.
  - Usa o tracking nativo do Ultralytics (model.track) para identificar
    quando uma peca "nova" aparece, em vez de uma maquina de estados
    baseada numa classe "vazio" artificial — a ausencia de deteccao na
    cena ja significa "vazio" por conta propria.
  - Conta parafusos dentro da area de cada peca detectada e compara com a
    quantidade esperada por estacao, para decidir OK/alerta.

ATENCAO: a deteccao de parafuso neste primeiro modelo foi treinada com
pouquissimos exemplos (dataset ainda nao tem a sessao de captura dedicada
de parafusos). Trate a contagem de parafusos como PRELIMINAR ate o modelo
ser retreinado com mais dados dessa classe — a deteccao da peca (cor) e o
indicador confiavel deste primeiro teste.

Uso:
    python infer_webcam_yolo.py --model ./runs_yolo/lean_lab_v1/weights/best.pt \
        --estacao camada_verde --parafusos_esperados 4 --api_url http://localhost:8000

Pressione "q" para encerrar.
"""
import argparse
import csv
import time
from datetime import datetime
from pathlib import Path

import cv2
import requests
from ultralytics import YOLO

CONFIDENCE_THRESHOLD = 0.5  # confianca minima para considerar uma deteccao valida
CAMADA_CLASSES = {"camada_base", "camada_verde", "camada_amarela", "camada_azul", "camada_vermelha"}
PARAFUSO_CLASS = "parafuso"


def log_event(
    api_url, csv_backup_path, estacao, classe_detectada, status, ciclo_segundos, parafusos_detectados, parafusos_esperados
):
    """
    Envia o evento para a API do backend (fase2-mvp/backend). Se a API estiver
    inacessivel (ex.: instabilidade do hotspot), o evento cai em um CSV de
    backup local. Mesmo padrao usado no infer_webcam.py da Fase 1.
    """
    payload = {
        "estacao": estacao,
        "classe_detectada": classe_detectada,
        "status": status,
        "tempo_ciclo_s": ciclo_segundos,
        "parafusos_detectados": parafusos_detectados,
        "parafusos_esperados": parafusos_esperados,
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
            writer.writerow(
                ["timestamp", "estacao", "classe_detectada", "status", "tempo_ciclo_s", "parafusos_detectados"]
            )
        writer.writerow(
            [
                datetime.now().isoformat(),
                estacao,
                classe_detectada,
                status,
                f"{ciclo_segundos:.2f}",
                parafusos_detectados,
            ]
        )


def box_center_inside(inner_box, outer_box):
    """Verifica se o centro de inner_box (x1,y1,x2,y2) esta dentro de outer_box."""
    cx = (inner_box[0] + inner_box[2]) / 2
    cy = (inner_box[1] + inner_box[3]) / 2
    return outer_box[0] <= cx <= outer_box[2] and outer_box[1] <= cy <= outer_box[3]


def main():
    parser = argparse.ArgumentParser(description="Inferencia ao vivo via webcam (YOLO — Fase 2)")
    parser.add_argument("--model", required=True, help="Caminho para o best.pt gerado pelo train_yolo.py")
    parser.add_argument(
        "--estacao", required=True, help="Classe de camada esperada para esta estacao, ex.: camada_verde"
    )
    parser.add_argument(
        "--parafusos_esperados",
        type=int,
        default=4,
        help="TODO: confirmar a quantidade real esperada por estacao com a Renault (ver fase-2-plano.md, secao 4)",
    )
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--api_url", default="http://localhost:8000")
    parser.add_argument("--backup_file", default="eventos_backup_yolo.csv")
    args = parser.parse_args()

    if args.estacao not in CAMADA_CLASSES:
        raise SystemExit(f"'{args.estacao}' nao e uma classe de camada conhecida. Opcoes: {sorted(CAMADA_CLASSES)}")

    model = YOLO(args.model)
    class_names = model.names  # dict {indice: nome}

    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        raise SystemExit("Nao foi possivel abrir a webcam. Verifique o indice em --camera.")

    csv_path = Path(args.backup_file)
    contadas_ids = set()  # track IDs de peca ja contabilizados nesta sessao
    ciclo_inicio = time.time()

    print("Pressione 'q' para sair.")
    print(
        "[LEMBRETE] Contagem de parafuso ainda e preliminar neste modelo "
        "(poucos exemplos de treino) — nao confie nesse numero por enquanto.\n"
    )

    while True:
        ok, frame = cap.read()
        if not ok:
            print("Falha ao ler frame da webcam.")
            break

        # persist=True mantem os track IDs consistentes entre frames, para
        # sabermos quando uma peca "nova" aparece (em vez de recontar a
        # mesma peca parada em frente a camera).
        results = model.track(frame, persist=True, conf=CONFIDENCE_THRESHOLD, verbose=False)
        result = results[0]

        camada_detections = []  # (track_id, class_name, box_xyxy, conf)
        parafuso_boxes = []

        if result.boxes is not None and result.boxes.id is not None:
            for box, track_id, cls_idx, conf in zip(
                result.boxes.xyxy.tolist(),
                result.boxes.id.tolist(),
                result.boxes.cls.tolist(),
                result.boxes.conf.tolist(),
            ):
                class_name = class_names.get(int(cls_idx), f"classe_{int(cls_idx)}")
                if class_name in CAMADA_CLASSES:
                    camada_detections.append((int(track_id), class_name, box, conf))
                elif class_name == PARAFUSO_CLASS:
                    parafuso_boxes.append(box)

        # Desenha as deteccoes na tela, para acompanhamento visual
        annotated = result.plot()

        for track_id, class_name, box, conf in camada_detections:
            if track_id in contadas_ids:
                continue  # peca ja contabilizada nesta sessao, so faz parte da cena

            # Peca nova detectada pela primeira vez: conta o evento
            contadas_ids.add(track_id)
            agora = time.time()
            tempo_ciclo = agora - ciclo_inicio
            ciclo_inicio = agora

            parafusos_na_peca = sum(1 for p_box in parafuso_boxes if box_center_inside(p_box, box))
            completo = parafusos_na_peca >= args.parafusos_esperados

            if class_name == args.estacao and completo:
                status = "OK"
            elif class_name != args.estacao:
                status = "ALERTA_CAMADA_INCORRETA"
            else:
                status = "ALERTA_PARAFUSOS_INSUFICIENTES"

            log_event(
                args.api_url,
                csv_path,
                args.estacao,
                class_name,
                status,
                tempo_ciclo,
                parafusos_na_peca,
                args.parafusos_esperados,
            )
            print(
                f"[EVENTO] track_id={track_id} classe={class_name} "
                f"parafusos_detectados={parafusos_na_peca}/{args.parafusos_esperados} status={status} "
                f"as {datetime.now().strftime('%H:%M:%S')}"
            )

        cv2.putText(
            annotated,
            f"Estacao esperada: {args.estacao} | Pecas contadas: {len(contadas_ids)}",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            2,
        )
        cv2.imshow("Estacao - Fase 2 (YOLO)", annotated)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()
    print(f"\nEventos enviados para: {args.api_url} (backup local, se usado, em: {csv_path.resolve()})")


if __name__ == "__main__":
    main()
