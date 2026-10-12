<#
.SYNOPSIS
    Sobe o backend, o dashboard e a inferencia ao vivo da Fase 2, cada um no
    seu lugar, com um unico comando.

.DESCRIPTION
    Isto so EMPACOTA os mesmos comandos documentados no README (secoes 4, 5 e
    6) -- nao faz nada que eles nao fizessem manualmente. Para depurar uma
    parte isolada (ex.: so o backend, para testar com curl), continue usando
    os comandos separados do README; este script e so para o dia a dia, rodar
    tudo de uma vez.

    O que faz, em ordem:
      1. Abre o backend (uvicorn) numa janela PowerShell separada.
      2. Espera a API responder em /health (ate ~45s) antes de continuar.
      3. Abre o dashboard (streamlit) em outra janela separada.
      4. Roda a inferencia pela webcam NESTA janela (em primeiro plano, para
         voce ver a janela da camera e poder apertar 'q' para sair) -- a
         menos que -PularCamera seja usado.

    Backend e dashboard ficam rodando nas janelas deles mesmo depois que a
    webcam for fechada -- feche as janelas manualmente, ou rode parar.ps1
    para derrubar os dois pelas portas (8000 e 8501).

    Usa o venv unico desta pasta (venv\Scripts\python.exe), que ja tem
    fastapi/uvicorn/streamlit/ultralytics instalados juntos nesta maquina.
    Se voce optou por venvs separados em backend\ e dashboard\ (como o README
    tambem documenta), use -PythonBackend/-PythonDashboard para apontar para
    eles.

.PARAMETER Estacao
    Classe de camada esperada nesta estacao (ex.: camada_verde, camada_amarela).
    Obrigatorio -- mesmo argumento de --estacao no infer_webcam_yolo.py.

.PARAMETER Model
    Caminho do best.pt a usar. Se omitido, usa automaticamente o treino mais
    recente em runs_yolo\*\weights\best.pt (pela data de modificacao).

.PARAMETER ApiUrl
    URL do backend. Padrao http://127.0.0.1:8000 -- de propósito NAO "localhost": em alguns Windows
    "localhost" resolve para ::1 (IPv6) primeiro, e como o backend so escuta IPv4 (--host 0.0.0.0),
    cada chamada perde ~2s tentando IPv6 antes de cair para IPv4 (confirmado nesta maquina: ~2s a mais
    por requisicao, e o health-check deste script demorava bem mais que o necessario por causa disso).

.PARAMETER Camera
    Indice da webcam (--camera do infer_webcam_yolo.py). Padrao 0.

.PARAMETER IgnorarClasses
    Repassado como --ignorar_classes (ex.: "encaixe_hexagono,encaixe_capsula").

.PARAMETER ModeloVersao
    Repassado como --modelo_versao. Se omitido, o proprio infer_webcam_yolo.py
    deduz do caminho de --model.

.PARAMETER PularBackend
    Nao abre o backend (use se ele ja estiver rodando em outra janela).

.PARAMETER PularDashboard
    Nao abre o dashboard.

.PARAMETER PularCamera
    Sobe so backend + dashboard, sem rodar a camera (ex.: para so revisar o dashboard com dados ja
    existentes, ou preparar o ambiente e rodar infer_webcam_yolo.py manualmente depois). Com isso,
    -Estacao deixa de ser obrigatorio.

.PARAMETER PythonBackend
.PARAMETER PythonDashboard
.PARAMETER PythonCamera
    Caminho alternativo para o python.exe de cada parte, se nao estiver tudo
    no venv unico desta pasta (padrao: venv\Scripts\python.exe para os tres).

.EXAMPLE
    .\iniciar.ps1 -Estacao camada_verde

.EXAMPLE
    .\iniciar.ps1 -Estacao camada_amarela -IgnorarClasses "encaixe_hexagono,encaixe_capsula"

.EXAMPLE
    # Backend ja estava rodando numa janela separada; so sobe dashboard + camera
    .\iniciar.ps1 -Estacao camada_azul -PularBackend

.EXAMPLE
    # So sobe backend + dashboard, sem camera -- para revisar dados existentes
    .\iniciar.ps1 -PularCamera
#>
[CmdletBinding()]
param(
    [string]$Estacao,

    [string]$Model,
    [string]$ApiUrl = "http://127.0.0.1:8000",
    [int]$Camera = 0,
    [string]$IgnorarClasses = "",
    [string]$ModeloVersao,

    [switch]$PularBackend,
    [switch]$PularDashboard,
    [switch]$PularCamera,

    [string]$PythonBackend,
    [string]$PythonDashboard,
    [string]$PythonCamera
)

$ErrorActionPreference = "Stop"
$raiz = $PSScriptRoot

if (-not $PularCamera -and -not $Estacao) {
    throw "-Estacao e obrigatorio (ex.: -Estacao camada_verde), a menos que voce use -PularCamera."
}

function Resolver-Python([string]$caminhoPedido, [string]$rotulo) {
    $caminho = if ($caminhoPedido) { $caminhoPedido } else { Join-Path $raiz "venv\Scripts\python.exe" }
    if (-not (Test-Path $caminho)) {
        throw "Python de '$rotulo' nao encontrado em '$caminho'. Rode 'python -m venv venv' e " +
              "'pip install -r requirements.txt' primeiro (ver README, secao 1), ou passe o caminho certo."
    }
    return (Resolve-Path $caminho).Path
}

$pyBackend = Resolver-Python $PythonBackend "backend"
$pyDashboard = Resolver-Python $PythonDashboard "dashboard"
if (-not $PularCamera) {
    $pyCamera = Resolver-Python $PythonCamera "camera"

    if (-not $Model) {
        $achado = Get-ChildItem -Path (Join-Path $raiz "runs_yolo\*\weights\best.pt") -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTime -Descending | Select-Object -First 1
        if (-not $achado) {
            throw "Nenhum best.pt encontrado em runs_yolo\*\weights\. Treine um modelo primeiro (README, secao 3) " +
                  "ou passe -Model apontando para um .pt existente."
        }
        $Model = $achado.FullName
        Write-Host "[iniciar] --model nao informado; usando o treino mais recente: $Model" -ForegroundColor DarkGray
    }
}

if (-not $PularBackend) {
    Write-Host "[iniciar] Abrindo backend (uvicorn) em nova janela..." -ForegroundColor Cyan
    $backendDir = Join-Path $raiz "backend"
    Start-Process powershell -ArgumentList @(
        "-NoExit", "-Command",
        "Set-Location '$backendDir'; & '$pyBackend' -m uvicorn main:app --reload --host 0.0.0.0 --port 8000"
    ) | Out-Null

    # uvicorn --reload sobe um processo observador + um worker -- mais lento
    # para iniciar que uvicorn "puro", principalmente em notebook com pouca
    # RAM. 45 tentativas de 1s (~45s) deu folga suficiente nos testes aqui;
    # aumente se sua maquina for mais lenta ainda.
    Write-Host "[iniciar] Aguardando a API responder em $ApiUrl/health (pode levar uns 10-20s)..." -ForegroundColor DarkGray
    $noAr = $false
    for ($i = 0; $i -lt 45; $i++) {
        try {
            $resp = Invoke-WebRequest -Uri "$ApiUrl/health" -TimeoutSec 2 -UseBasicParsing
            if ($resp.StatusCode -eq 200) { $noAr = $true; break }
        } catch {}
        Start-Sleep -Seconds 1
        if ($i % 5 -eq 4) { Write-Host "[iniciar] ainda esperando ($($i + 1)s)..." -ForegroundColor DarkGray }
    }
    if ($noAr) {
        Write-Host "[iniciar] Backend no ar." -ForegroundColor Green
    } else {
        Write-Host "[iniciar] Backend ainda nao respondeu apos 45s -- confira a janela dele, pode ter dado erro. Continuando mesmo assim." -ForegroundColor Yellow
    }
} else {
    Write-Host "[iniciar] -PularBackend: assumindo que o backend ja esta rodando em $ApiUrl." -ForegroundColor DarkGray
}

if (-not $PularDashboard) {
    Write-Host "[iniciar] Abrindo dashboard (streamlit) em nova janela..." -ForegroundColor Cyan
    $dashDir = Join-Path $raiz "dashboard"
    Start-Process powershell -ArgumentList @(
        "-NoExit", "-Command",
        "Set-Location '$dashDir'; & '$pyDashboard' -m streamlit run app.py"
    ) | Out-Null
}

Write-Host ""
Write-Host "[iniciar] Backend : $ApiUrl  (docs em $ApiUrl/docs)" -ForegroundColor Green
Write-Host "[iniciar] Dashboard: http://localhost:8501" -ForegroundColor Green

if ($PularCamera) {
    Write-Host "[iniciar] -PularCamera: backend e dashboard no ar; camera nao foi iniciada." -ForegroundColor DarkGray
    Write-Host "[iniciar] Rode infer_webcam_yolo.py manualmente quando quiser (ver README, secao 6)." -ForegroundColor DarkGray
    Write-Host "[iniciar] Para derrubar backend/dashboard depois: .\parar.ps1" -ForegroundColor DarkGray
    exit 0
}

Write-Host "[iniciar] Iniciando a camera (estacao: $Estacao, modelo: $Model)..." -ForegroundColor Cyan
Write-Host "[iniciar] Pressione 'q' na janela da camera para encerrar. Backend/dashboard continuam rodando" -ForegroundColor DarkGray
Write-Host "[iniciar] nas janelas deles ate voce fechar manualmente, ou rode .\parar.ps1" -ForegroundColor DarkGray
Write-Host ""

$argsCamera = @("infer_webcam_yolo.py", "--model", $Model, "--estacao", $Estacao, "--api_url", $ApiUrl, "--camera", $Camera)
if ($IgnorarClasses) { $argsCamera += @("--ignorar_classes", $IgnorarClasses) }
if ($ModeloVersao) { $argsCamera += @("--modelo_versao", $ModeloVersao) }

Push-Location $raiz
try {
    & $pyCamera @argsCamera
} finally {
    Pop-Location
}
