import collections
import queue
import threading
import time

import discord
from discord.opus import OPUS_SILENCE

FRAMES_PER_SECOND = 50  # cada pacote Opus tem 20 ms

# Reconecta sozinho se o servidor da rádio derrubar a conexão
FFMPEG_BEFORE_OPTIONS = '-reconnect 1 -reconnect_streamed 1 -reconnect_on_network_error 1 -reconnect_delay_max 5'


class Assinatura(discord.AudioSource):
    """Fonte de áudio de um servidor (guild) ligada a uma estação compartilhada.

    Recebe os pacotes Opus já codificados e mantém um buffer próprio. Se o buffer
    esvaziar, envia silêncio em vez de travar a thread de envio do Discord.
    """

    def __init__(self, estacao, max_seconds=6, prebuffer_seconds=2):
        self.estacao = estacao
        self.underruns = 0
        self._queue = queue.Queue(maxsize=max_seconds * FRAMES_PER_SECOND)
        self._prebuffer = prebuffer_seconds * FRAMES_PER_SECOND
        self._ready = False
        self._closed = False

    def push(self, pacote):
        """Chamado pela thread da estação. Se o buffer encher, descarta o pacote mais antigo."""
        try:
            self._queue.put_nowait(pacote)
        except queue.Full:
            try:
                self._queue.get_nowait()
                self._queue.put_nowait(pacote)
            except (queue.Empty, queue.Full):
                pass

    def read(self):
        if self._closed:
            return b''
        if not self._ready:
            if self._queue.qsize() < self._prebuffer:
                return OPUS_SILENCE
            self._ready = True
        try:
            return self._queue.get_nowait()
        except queue.Empty:
            self.underruns += 1
            return OPUS_SILENCE

    @property
    def buffered_seconds(self):
        return self._queue.qsize() / FRAMES_PER_SECOND

    def is_opus(self):
        return True

    def cleanup(self):
        self._closed = True
        self.estacao.remover(self)


class EstacaoCompartilhada:
    """Uma única conexão com a rádio e um único FFmpeg (decodifica + codifica Opus),
    distribuindo os mesmos pacotes para todos os servidores que estiverem ouvindo.

    Só roda enquanto houver ouvintes: o primeiro assinante liga, o último desliga.
    """

    def __init__(self, nome, url, bitrate=128):
        self.nome = nome
        self.url = url
        self.bitrate = bitrate
        self._assinaturas = set()
        self._recentes = collections.deque(maxlen=2 * FRAMES_PER_SECOND)  # últimos 2 s, para quem entra depois
        self._lock = threading.Lock()
        self._parar = threading.Event()  # um evento por execução da thread
        self._thread = None
        self._source = None

    @property
    def ouvintes(self):
        with self._lock:
            return len(self._assinaturas)

    def assinar(self):
        assinatura = Assinatura(self)
        with self._lock:
            for pacote in self._recentes:  # entra com 2 s de áudio e começa a tocar na hora
                assinatura.push(pacote)
            self._assinaturas.add(assinatura)
            if self._thread is None or not self._thread.is_alive() or self._parar.is_set():
                self._parar = threading.Event()
                self._thread = threading.Thread(target=self._executar, args=(self._parar,), daemon=True,
                                                name=f'estacao-{self.nome}')
                self._thread.start()
        return assinatura

    def remover(self, assinatura):
        source = None
        with self._lock:
            self._assinaturas.discard(assinatura)
            if not self._assinaturas:
                self._parar.set()
                self._recentes.clear()
                source, self._source = self._source, None
        if source:
            source.cleanup()  # encerra o FFmpeg; a thread da estação sai sozinha

    def _distribuir(self, pacote):
        with self._lock:
            self._recentes.append(pacote)
            assinaturas = list(self._assinaturas)
        for a in assinaturas:
            a.push(pacote)

    def _executar(self, parar):
        espera = 1
        while not parar.is_set():
            inicio = time.monotonic()
            source = None
            try:
                source = discord.FFmpegOpusAudio(self.url, bitrate=self.bitrate, before_options=FFMPEG_BEFORE_OPTIONS)
                with self._lock:
                    if parar.is_set():
                        break
                    self._source = source
                while not parar.is_set():
                    pacote = source.read()
                    if not pacote:
                        break
                    self._distribuir(pacote)
            except Exception as e:
                print(f'[{self.nome}] erro no stream: {e}')
            finally:
                if source:
                    try:
                        source.cleanup()
                    except Exception:
                        pass
            if parar.is_set():
                break
            # O stream caiu: tenta de novo com espera crescente (reinicia a espera se durou mais de 30 s)
            espera = 1 if time.monotonic() - inicio > 30 else min(espera * 2, 15)
            print(f'[{self.nome}] stream encerrado, reconectando em {espera}s')
            parar.wait(espera)
