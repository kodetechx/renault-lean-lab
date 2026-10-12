<#
.SYNOPSIS
    Encerra o backend e o dashboard da Fase 2, iniciados por iniciar.ps1 (ou
    manualmente), derrubando quem estiver escutando nas portas deles.

.DESCRIPTION
    iniciar.ps1 abre o backend e o dashboard cada um na sua propria janela
    PowerShell; fechar so a janela da camera (ou apertar 'q' nela) nao
    encerra as outras duas. Este script acha o processo que esta ouvindo em
    cada porta e encerra ele E toda a arvore de processos filhos --
    equivalente a fechar as janelas manualmente.

    Por que a arvore inteira, e nao so o processo da porta: o backend roda
    com 'uvicorn --reload', que no Windows sobe um processo supervisor e um
    worker filho (via multiprocessing) escutando a mesma porta. Matar so o
    processo que a porta reporta pode derrubar o supervisor e deixar o
    worker filho vivo, segurando a porta -- confirmado na pratica neste
    projeto (o backend "voltava sozinho" depois de matar so um PID). Como o
    SO pode reportar o supervisor OU o worker como dono da porta, o script
    primeiro sobe ate o processo mais acima com o MESMO nome (a cadeia
    supervisor/worker), e so entao desce matando toda a arvore -- sem passar
    da janela/terminal que chamou o script (nome diferente, nao sobe mais).

.PARAMETER PortaBackend
    Porta do backend a derrubar. Padrao 8000.

.PARAMETER PortaDashboard
    Porta do dashboard (Streamlit) a derrubar. Padrao 8501.

.EXAMPLE
    .\parar.ps1

.EXAMPLE
    .\parar.ps1 -PortaBackend 8010   # se voce rodou o backend numa porta diferente
#>
param(
    [int]$PortaBackend = 8000,
    [int]$PortaDashboard = 8501
)

function Obter-Raiz-Real([int]$pid_) {
    # Get-NetTCPConnection pode reportar o worker (filho) OU o supervisor (pai)
    # do 'uvicorn --reload' como dono da porta, dependendo da versao/SO. Sobe
    # a arvore enquanto o processo pai tiver o MESMO nome do processo atual
    # (ex.: python.exe -> python.exe, a cadeia supervisor/worker), parando
    # assim que o nome mudar (ex.: a janela powershell.exe que hospeda tudo) --
    # isso evita subir alem da familia do uvicorn e matar a janela/terminal
    # que chamou o script.
    $atual = Get-CimInstance Win32_Process -Filter "ProcessId=$pid_" -ErrorAction SilentlyContinue
    if (-not $atual) { return $pid_ }
    $nomeOriginal = $atual.Name
    while ($true) {
        $pai = Get-CimInstance Win32_Process -Filter "ProcessId=$($atual.ParentProcessId)" -ErrorAction SilentlyContinue
        if (-not $pai -or $pai.Name -ne $nomeOriginal) { break }
        $atual = $pai
    }
    return $atual.ProcessId
}

function Obter-Arvore([int]$raizPid) {
    # Devolve o PID dado + todos os descendentes (filhos, netos, ...), buscando nivel por nivel.
    $todos = @($raizPid)
    $fronteira = @($raizPid)
    while ($fronteira.Count -gt 0) {
        $filhos = foreach ($p in $fronteira) {
            Get-CimInstance Win32_Process -Filter "ParentProcessId=$p" -ErrorAction SilentlyContinue
        }
        $novos = @($filhos | Select-Object -ExpandProperty ProcessId -Unique | Where-Object { $_ -notin $todos })
        $todos += $novos
        $fronteira = $novos
    }
    return $todos
}

function Parar-Porta([int]$porta, [string]$rotulo) {
    $conexoes = Get-NetTCPConnection -LocalPort $porta -State Listen -ErrorAction SilentlyContinue
    if (-not $conexoes) {
        Write-Host "[parar] $rotulo (porta $porta): nada rodando." -ForegroundColor DarkGray
        return
    }
    $raizes = $conexoes | Select-Object -ExpandProperty OwningProcess -Unique
    $alvos = @()
    foreach ($raizPid in $raizes) {
        $raizReal = Obter-Raiz-Real $raizPid
        $alvos += Obter-Arvore $raizReal
    }
    $alvos = $alvos | Select-Object -Unique

    foreach ($procId in $alvos) {
        $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
        if (-not $proc) { continue }
        try {
            Stop-Process -Id $procId -Force -ErrorAction Stop
            Write-Host "[parar] $rotulo (porta $porta): processo $($proc.ProcessName) (PID $procId) encerrado." -ForegroundColor Green
        } catch {
            Write-Host "[parar] $rotulo (porta $porta): nao foi possivel encerrar o PID $procId ($_)." -ForegroundColor Yellow
        }
    }

    Start-Sleep -Milliseconds 500
    if (Get-NetTCPConnection -LocalPort $porta -State Listen -ErrorAction SilentlyContinue) {
        Write-Host "[parar] $rotulo (porta $porta): algo ainda esta escutando (pode ter respawnado). Rode .\parar.ps1 de novo." -ForegroundColor Yellow
    }
}

Parar-Porta -porta $PortaBackend -rotulo "Backend"
Parar-Porta -porta $PortaDashboard -rotulo "Dashboard"

Write-Host ""
Write-Host "[parar] Se a janela da camera (infer_webcam_yolo.py) ainda estiver aberta, feche-a com 'q' separadamente." -ForegroundColor DarkGray
