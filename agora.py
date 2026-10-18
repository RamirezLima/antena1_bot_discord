import asyncio
import itertools
from dataclasses import dataclass
from typing import Optional

import aiohttp

API = 'https://www.antena1.com.br/api/v1/aovivo/getCurrentSongInfo/'
USER_AGENT = 'Antena1DiscordBot/1.0'
INTERVALO = 10   # a API responde com cache-control max-age=5; consultar mais rápido não traz nada novo
ESPERA_MAX = 120  # teto da espera crescente quando a API falha


@dataclass(frozen=True)
class Musica:
    inicio: str
    artista: str
    titulo: str
    album: Optional[str] = None
    ano: Optional[int] = None
    capa: Optional[str] = None
    tipo: str = 'music'


def _texto(valor):
    return valor.strip() if isinstance(valor, str) and valor.strip() else None


def interpretar(data):
    """Converte a resposta da API em Musica. A API usa `false` para campos ausentes."""
    if not isinstance(data, dict) or not data.get('time'):
        return None
    capa = _texto(data.get('cover'))
    return Musica(
        inicio=data['time'],
        artista=_texto(data.get('artist')) or 'Antena 1',
        titulo=_texto(data.get('song')) or 'Programação',
        album=_texto(data.get('album')),
        ano=data['year'] if type(data.get('year')) is int and data['year'] > 0 else None,  # `false` também é int
        capa=capa if capa and capa.startswith('https://') else None,
        tipo=_texto(data.get('metaType')) or 'music',
    )


class Acompanhante:
    """Consulta a música atual de um metaId da Antena 1 e avisa os ouvintes quando ela muda.

    Faz UMA requisição por intervalo, não importa quantos servidores estejam ouvindo, e só
    enquanto houver pelo menos um inscrito (a tarefa nasce no primeiro e morre no último).
    """

    def __init__(self, meta_id, intervalo=INTERVALO, buscar=None):
        self.meta_id = meta_id
        self.intervalo = intervalo
        self.atual = None
        self.requisicoes = 0
        self._ouvintes = {}
        self._tarefa = None
        self._ids = itertools.count(1)
        self._buscar = buscar or self._buscar_http

    @property
    def ativo(self):
        return self._tarefa is not None and not self._tarefa.done()

    def inscrever(self, callback):
        """callback(musica) é uma corrotina. Se já houver música conhecida, ela é entregue na hora."""
        token = next(self._ids)
        self._ouvintes[token] = callback
        if self.atual:
            asyncio.get_running_loop().create_task(self._avisar(callback, self.atual))
        if not self.ativo:
            self._tarefa = asyncio.get_running_loop().create_task(self._executar())
        return token

    def desinscrever(self, token):
        self._ouvintes.pop(token, None)
        if not self._ouvintes and self._tarefa:
            self._tarefa.cancel()
            self._tarefa = None
            self.atual = None  # sem ouvintes o dado envelhece; o próximo inscrito força uma consulta nova

    async def _buscar_http(self, sessao):
        async with sessao.get(API + self.meta_id) as resp:
            resp.raise_for_status()
            corpo = await resp.json(content_type=None)
        return interpretar(corpo.get('data')) if corpo.get('status') == 'success' else None

    async def _avisar(self, callback, musica):
        try:
            await callback(musica)
        except Exception as e:
            print(f'[agora:{self.meta_id}] erro ao avisar ouvinte: {e!r}')

    async def _executar(self):
        espera = self.intervalo
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(headers={'User-Agent': USER_AGENT}, timeout=timeout) as sessao:
            while self._ouvintes:
                try:
                    self.requisicoes += 1
                    musica = await self._buscar(sessao)
                    espera = self.intervalo
                    if musica and (not self.atual or musica.inicio != self.atual.inicio):
                        self.atual = musica
                        for callback in list(self._ouvintes.values()):
                            asyncio.get_running_loop().create_task(self._avisar(callback, musica))
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    espera = min(espera * 2, ESPERA_MAX)
                    print(f'[agora:{self.meta_id}] falha na consulta ({e!r}); nova tentativa em {espera}s')
                await asyncio.sleep(espera)
