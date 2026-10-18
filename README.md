<div align="center">

# 📻 Antena 1 Bot

**Bot de Discord que toca as estações da rádio Antena 1 em canais de voz, com painel interativo e "Tocando agora".**

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![discord.py](https://img.shields.io/badge/discord.py-2.7-5865F2?logo=discord&logoColor=white)
![FFmpeg](https://img.shields.io/badge/FFmpeg-required-007808?logo=ffmpeg&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

</div>

> ⚠️ Projeto independente e **não oficial**: não é afiliado nem endossado pela Antena 1. Os streams e a API de "música atual" pertencem à emissora e são usados apenas para reproduzir o conteúdo público do próprio site.

---

## ✨ Funcionalidades

- 🎧 **4 estações** públicas da Antena 1 (Normal, Baixo, HD e Espacial)
- 🎛️ **Painel interativo** com menu suspenso para trocar de estação e botões de **Pausar / Retomar / Parar**
- 🎵 **Tocando agora**: título, artista, álbum, ano e capa, atualizados sozinhos a cada troca de música
- ⚡ **Slash commands** (`/antenas`) e comandos clássicos com prefixo (`!antenas`)
- 🔁 **Reconexão automática** se o stream da rádio cair
- 🛡️ **Buffer de áudio** para evitar cortes por oscilação de rede ou CPU
- 🌐 **Multi-servidor eficiente**: uma única conexão por estação, compartilhada entre todos os servidores
- 🚪 Sai do canal sozinho quando ninguém mais está ouvindo

## 🕹️ Comandos

Todos funcionam como slash command (`/`) e com prefixo (`!`).

| Comando | O que faz |
|---|---|
| `/antenas` | Lista as estações com um menu para escolher |
| `/antena <número>` | Toca a estação pelo número da lista (ex.: `/antena 2`) |
| `/antena1` | Atalho para a estação Normal |
| `/pausar` · `/resumir` | Pausa e retoma a reprodução |
| `/parar` | Para e desconecta do canal de voz |
| `/ping` | Verifica se o bot está online |

## 📡 Estações

| # | Estação | Descrição | Variável de ambiente |
|---|---|---|---|
| 1 | 📻 Normal | Programação padrão da Antena 1 | `URL-ANTENA1` |
| 2 | 📶 Baixo | Mesma programação, leve para internet lenta | `URL-ANTENA1-BAIXO` |
| 3 | 💎 HD | Programação padrão em alta qualidade | `URL-ANTENA1-HD` |
| 4 | 🚀 Espacial | Sucessos internacionais em uma estação à parte | `URL-ANTENA1-ESPACIAL` |

## 🚀 Como rodar

### Requisitos

- Python **3.10+**
- **FFmpeg** instalado e disponível no `PATH`
- Um bot criado no [Discord Developer Portal](https://discord.com/developers/applications)

### 1. Criar o bot no Discord

1. No Developer Portal, crie uma aplicação e adicione um **Bot**.
2. Em **Bot → Privileged Gateway Intents**, ative **Message Content Intent**.
3. Copie o **token** (Reset Token).
4. Em **OAuth2 → URL Generator**, marque os escopos `bot` e `applications.commands` e as permissões **Connect**, **Speak**, **Send Messages** e **Embed Links**. Use o link gerado para convidar o bot ao seu servidor.

### 2. Instalar

```bash
git clone https://github.com/RamirezLima/antena1_bot_discord.git
cd antena1_bot_discord

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configurar

```bash
cp .env.example .env
```

Edite o `.env` e preencha o `TOKEN`. As URLs das estações são opcionais.

### 4. Executar

```bash
python main.py
```

## ⚙️ Configuração

Tudo é lido de variáveis de ambiente (ou de um arquivo `.env`), então o bot roda em qualquer ambiente: máquina local, VPS, container ou plataforma de hospedagem.

| Variável | Obrigatória | Descrição |
|---|:---:|---|
| `TOKEN` | ✅ | Token do bot do Discord |
| `URL-ANTENA1` | ❌ | URL de áudio da estação Normal |
| `URL-ANTENA1-BAIXO` | ❌ | URL de áudio da estação Baixo |
| `URL-ANTENA1-HD` | ❌ | URL de áudio da estação HD |
| `URL-ANTENA1-ESPACIAL` | ❌ | URL de áudio da estação Espacial |
| `PORT` | ❌ | Porta do servidor web de status (padrão `3000`) |

As variáveis de URL são opcionais: se não existirem (ou estiverem vazias), o bot usa o valor padrão definido no código.

> 💡 Nomes com hífen não podem ser usados com `export` no bash. Defina-os no `.env`, no painel da sua hospedagem ou com `env 'URL-ANTENA1-HD=...' python main.py`.

### Hospedagem

O bot precisa de um processo Python sempre ligado e do FFmpeg no sistema. Ele também sobe um pequeno servidor web (`GET /` responde `Bot online!`) na porta `PORT`, útil para health checks ou para plataformas que exigem uma porta HTTP aberta. O comando de inicialização é simplesmente `python main.py`.

## 🧠 Como funciona

```
 Servidor A ─┐                                    ┌─ FFmpeg (1 por estação) ◄── stream da Antena 1
 Servidor B ─┼── Assinaturas (buffer próprio) ◄───┤      decodifica + codifica Opus uma única vez
 Servidor C ─┘                                    └─ Pacotes Opus distribuídos a todos os ouvintes

 Servidores ouvindo ──► 1 consulta de "música atual" por estação (a cada 10 s, só enquanto há ouvintes)
```

- **Fonte compartilhada** ([`broadcast.py`](broadcast.py)): cada estação mantém um único FFmpeg e uma única conexão com a rádio, não importa quantos servidores estejam ouvindo. O processo liga com o primeiro ouvinte e desliga com o último.
- **Buffer por ouvinte**: cada servidor tem seu próprio buffer. Quem entra depois começa a tocar na hora, com 2 s de áudio já guardados. Se o buffer esvaziar, o bot envia silêncio em vez de travar.
- **Tocando agora** ([`agora.py`](agora.py)): uma única tarefa por estação consulta a música atual a cada 10 s, e só enquanto houver alguém ouvindo. A pausa suspende a consulta, e ela para quando o bot sai do canal. Se a API falhar, o bot espera cada vez mais entre as tentativas e mantém a última música na tela.

## 🗂️ Estrutura

```
.
├── main.py            # Bot, comandos, painel interativo e configuração das estações
├── broadcast.py       # Fonte de áudio compartilhada por estação (FFmpeg + buffer)
├── agora.py           # Consulta compartilhada da música atual
├── requirements.txt   # Dependências
└── .env.example       # Modelo das variáveis de ambiente
```

## 🔒 Segurança

- **Nunca** versione o `.env` nem publique o token do bot. O `.env` já está no `.gitignore`.
- Se um token vazar, gere outro imediatamente em **Developer Portal → Bot → Reset Token**.

## ⚠️ Observações

- A API de "música atual" é a mesma usada pelo player do site da Antena 1. Ela **não é documentada** e pode mudar sem aviso. Se isso acontecer, o bot continua tocando normalmente e apenas deixa de mostrar a música atual.
- O áudio chega ao Discord com alguns segundos de atraso em relação ao ao vivo, por causa do buffer.

## 📄 Licença

Distribuído sob a licença MIT. Veja o arquivo [LICENSE](LICENSE). A licença cobre apenas o código deste repositório: o nome, a marca, os streams e a API da Antena 1 pertencem à emissora.
