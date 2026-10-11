"""
infer_webcam_yolo.py

Roda o modelo YOLO treinado (train_yolo.py) ao vivo, a partir da webcam,
simulando o funcionamento de uma estacao — versao Fase 2 (deteccao de
objeto), substituindo o infer_webcam.py da Fase 1 (classificacao).

Diferencas principais em relacao ao infer_webcam.py da Fase 1:
  - Detecta MULTIPLAS pecas no mesmo frame (nao um unico rotulo por frame),
    resolvendo a limitacao do MobileNetV2 discutida no planejamento da
    Fase 2.
  - Usa o tracking nativo do Ultralytics (model.track) para identificar
    quando uma peca "nova" aparece, em vez de uma maquina de estados
    baseada numa classe "vazio" artificial — a ausencia de deteccao na
    cena ja significa "vazio" por conta propria.
  - Conta parafusos E pecas de encaixe, mas SO quando o centro da caixa
    detectada cai DENTRO da caixa da peca (camada) — ver box_center_inside().
    Isso evita contar um parafuso solto na mesa, fora da peca, como se
    fizesse parte da montagem (pergunta respondida em 04/10/2026, ver
    fase-2-plano.md).
  - A receita de completude (quantos parafusos, quais pecas de encaixe)
    varia por estacao, de acordo com a tabela confirmada com a Renault
    (fase-2-plano.md, secao 4) — nao e mais um numero fixo via
    --parafusos_esperados.
  - Permite desativar a deteccao de uma ou mais classes em tempo de
    inferencia (--ignorar_classes), sem precisar retreinar ou voltar a uma
    versao anterior do modelo — ver ESTACAO_RECEITA e a explicacao no
    cabecalho de --ignorar_classes abaixo.

ATENCAO: a deteccao de parafuso/encaixe depende da qualidade e quantidade
de anotacoes reais dessas classes no treino mais recente. Se o modelo ainda
nao foi retreinado com o lote 2 (parafuso + encaixe + multi-peca), trate a
contagem como PRELIMINAR — a deteccao da peca (cor) e o indicador mais
confiavel ate esse retreino ser validado (ver fase-2-plano.md, secao 3.1).

Uso:
    python infer_webcam_yolo.py --model ./runs_yolo/lean_lab_v2/weights/best.pt \
        --estacao camada_amarela --api_url http://localhost:8000

    # Desativando a deteccao de encaixe (ex.: se ela nao estiver confiavel
    # ainda, mas sem querer perder a deteccao de camada/parafuso):
    python infer_webcam_yolo.py --model ./runs_yolo/lean_lab_v2/weights/best.pt \
        --estacao camada_verde \
        --ignorar_classes encaixe_circular,encaixe_retangular,encaixe_hexagono,encaixe_capsula

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
ENCAIXE_CLASSES = {"encaixe_circular", "encaixe_retangular", "encaixe_hexagono", "encaixe_capsula"}

# Receita de completude por estacao, confirmada com a Renault em 20/09/2026
# (fase-2-plano.md, secao 4). "encaixe" e o conjunto de classes de encaixe
# que precisam TODAS aparecer dentro da peca — nao e so uma contagem, e uma
# checagem de identidade (as 4 formas certas, nao 4 pecas quaisquer).
ESTACAO_RECEITA = {
    "camada_base": {"parafusos": 0, "encaixe": set()},
    "camada_verde": {"parafusos": 4, "encaixe": set()},
    "camada_amarela": {"parafusos": 4, "encaixe": set(ENCAIXE_CLASSES)},
    "camada_azul": {"parafusos": 4, "encaixe": set()},
    "camada_vermelha": {"parafusos": 4, "encaixe": set(ENCAIXE_CLASSES)},
}


def log_event(api_url, csv_backup_path, estacao, classe_detectada, status, ciclo_segundos, parafusos_detectados, encaixes_detectados):
    """
    Envia o evento para a API do backend. Se a API estiver inacessivel
    (ex.: instabilidade do hotspot), o evento cai em um CSV de backup local.
    Mesmo padrao usado no infer_webcam.py da Fase 1.
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
            writer.writerow(
                [
                    "timestamp", "estacao", "classe_detectada", "status", "tempo_ciclo_s",
                    "parafusos_detectados", "encaixes_detectados",
                ]
            )
        writer.writerow(
            [
                datetime.now().isoformat(),
                estacao,
                classe_detectada,
                status,
                f"{ciclo_segundos:.2f}",
                parafusos_detectados,
                ",".join(sorted(encaixes_detectados)) if encaixes_detectados else "",
            ]
        )


def box_center_inside(inner_box, outer_box):
    """Verifica se o centro de inner_box (x1,y1,x2,y2) esta dentro de outer_box."""
    cx = (inner_box[0] + inner_box[2]) / 2
    cy = (inner_box[1] + inner_box[3]) / 2
    return outer_box[0] <= cx <= outer_box[2] and outer_box[1] <= cy <= outer_box[3]


def resolver_classes_a_manter(model_names, nomes_ignorados):
    """
    Traduz uma lista de NOMES de classe (ex.: ["encaixe_circular", "parafuso"])
    para os INDICES que o Ultralytics usa internamente, e devolve a lista dos
    indices a MANTER (todas menos as ignoradas).

    Isso permite "desligar" a deteccao de uma classe problematica sem
    retreinar nem voltar a uma versao anterior do .pt: o parametro
    `classes=` do model.track()/model.predict() filtra o que o modelo
    retorna, mesmo que ele continue "sabendo" detectar aquela classe
    internamente (os pesos nao mudam, so a saida é filtrada).
    """
    if not nomes_ignorados:
        return None  # None = nao filtra nada, comportamento padrao

    nomes_ignorados = set(nomes_ignorados)
    desconhecidos = nomes_ignorados - set(model_names.values())
    if desconhecidos:
        raise SystemExit(
            f"Classe(s) desconhecida(s) em --ignorar_classes: {sorted(desconhecidos)}. "
            f"Classes do modelo: {sorted(model_names.values())}"
        )

    indices_a_manter = [idx for idx, nome in model_names.items() if nome not in nomes_ignorados]
    if not indices_a_manter:
        raise SystemExit("--ignorar_classes removeria TODAS as classes do modelo. Revise a lista.")
    return indices_a_manter


def main():
    parser = argparse.ArgumentParser(description="Inferencia ao vivo via webcam (YOLO — Fase 2)")
    parser.add_argument("--model", required=True, help="Caminho para o best.pt gerado pelo train_yolo.py")
    parser.add_argument(
        "--estacao", required=True, help="Classe de camada esperada para esta estacao, ex.: camada_verde"
    )
    parser.add_argument(
        "--ignorar_classes",
        default="",
        help=(
            "Lista separada por virgula de classes para EXCLUIR da deteccao, sem retreinar nem reverter o "
            "modelo (ex.: 'encaixe_circular,encaixe_capsula'). Util se uma classe especifica ainda nao estiver "
            "confiavel o suficiente, mas as demais ja estiverem. A receita de completude da estacao (quantos "
            "parafusos/encaixes) nao muda sozinha so porque a classe foi ignorada aqui -- se voce ignorar uma "
            "classe de encaixe exigida pela estacao atual, ela nunca vai ser encontrada e o status vai sempre "
            "dar alerta de incompleto. Ajuste manualmente ESTACAO_RECEITA no codigo se quiser também relaxar "
            "a exigencia, em vez de so escondendo a deteccao."
        ),
    )
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--api_url", default="http://localhost:8000")
    parser.add_argument("--backup_file", default="eventos_backup_yolo.csv")
    args = parser.parse_args()

    if args.estacao not in ESTACAO_RECEITA:
        raise SystemExit(f"'{args.estacao}' nao e uma classe de camada conhecida. Opcoes: {sorted(ESTACAO_RECEITA)}")

    receita = ESTACAO_RECEITA[args.estacao]

    model = YOLO(args.model)
    class_names = model.names  # dict {indice: nome}

    nomes_ignorados = [n.strip() for n in args.ignorar_classes.split(",") if n.strip()]
    classes_a_manter = resolver_classes_a_manter(class_names, nomes_ignorados)
    if nomes_ignorados:
        print(f"[CONFIG] Ignorando deteccao de: {nomes_ignorados}")
        faltando_na_receita = receita["encaixe"] & set(nomes_ignorados)
        if faltando_na_receita or (receita["parafusos"] > 0 and PARAFUSO_CLASS in nomes_ignorados):
            print(
                "[AVISO] A estacao atual exige classe(s) que voce acabou de ignorar "
                f"({sorted(faltando_na_receita) + ([PARAFUSO_CLASS] if PARAFUSO_CLASS in nomes_ignorados and receita['parafusos'] > 0 else [])}). "
                "O status vai ficar sempre incompleto para essas pecas enquanto isso estiver ativo."
            )

    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        raise SystemExit("Nao foi possivel abrir a webcam. Verifique o indice em --camera.")

    csv_path = Path(args.backup_file)
    contadas_ids = set()  # track IDs de peca ja contabilizados nesta sessao
    ciclo_inicio = time.time()

    print("Pressione 'q' para sair.")
    print(f"[CONFIG] Estacao: {args.estacao} | Receita: {receita['parafusos']} parafuso(s)"
          + (f" + encaixe {sorted(receita['encaixe'])}" if receita["encaixe"] else ""))
    print(
        "[LEMBRETE] Trate a contagem de parafuso/encaixe como preliminar até confirmar que o "
        "retreino com o lote novo (parafuso + encaixe + multi-peça) já está sendo usado neste --model.\n"
    )

    while True:
        ok, frame = cap.read()
        if not ok:
            print("Falha ao ler frame da webcam.")
            break

        # persist=True mantem os track IDs consistentes entre frames, para
        # sabermos quando uma peca "nova" aparece (em vez de recontar a
        # mesma peca parada em frente a camera). classes=classes_a_manter
        # filtra a saida do modelo sem precisar retreinar (None = sem filtro).
        results = model.track(
            frame, persist=True, conf=CONFIDENCE_THRESHOLD, classes=classes_a_manter, verbose=False
        )
        result = results[0]

        camada_detections = []  # (track_id, class_name, box_xyxy, conf)
        parafuso_boxes = []
        encaixe_detections = []  # (class_name, box_xyxy)

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
                elif class_name in ENCAIXE_CLASSES:
                    encaixe_detections.append((class_name, box))

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

            # So conta parafuso/encaixe cujo CENTRO cai dentro da caixa da
            # peca -- um parafuso solto na mesa, fora da peca, nao entra
            # nessa contagem (pergunta respondida em 04/10/2026).
            parafusos_na_peca = sum(1 for p_box in parafuso_boxes if box_center_inside(p_box, box))
            encaixes_na_peca = {
                e_nome for e_nome, e_box in encaixe_detections if box_center_inside(e_box, box)
            }

            receita_estacao = ESTACAO_RECEITA.get(args.estacao, {"parafusos": 0, "encaixe": set()})
            parafuso_ok = parafusos_na_peca >= receita_estacao["parafusos"]
            encaixe_ok = receita_estacao["encaixe"].issubset(encaixes_na_peca)
            completo = parafuso_ok and encaixe_ok

            if class_name != args.estacao:
                status = "ALERTA_CAMADA_INCORRETA"
            elif not parafuso_ok:
                status = "ALERTA_PARAFUSOS_INSUFICIENTES"
            elif not encaixe_ok:
                status = "ALERTA_ENCAIXE_INCOMPLETO"
            else:
                status = "OK"

            log_event(
                args.api_url, csv_path, args.estacao, class_name, status, tempo_ciclo,
                parafusos_na_peca, encaixes_na_peca,
            )
            print(
                f"[EVENTO] track_id={track_id} classe={class_name} "
                f"parafusos={parafusos_na_peca}/{receita_estacao['parafusos']} "
                f"encaixe={sorted(encaixes_na_peca)}/{sorted(receita_estacao['encaixe'])} "
                f"status={status} as {datetime.now().strftime('%H:%M:%S')}"
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