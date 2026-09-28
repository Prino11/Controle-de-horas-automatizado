"""Única fronteira com a API externa; aceita cliente injetado em testes."""
import logging
from pathlib import Path

from pydantic import ValidationError
from config.settings import GEMINI_MODEL, gemini_api_key
from models.extracao import CartaoExtraido, LeituraCartao
from services.gemini_prompt import PROMPT, PROMPT_PAGINA

LOG = logging.getLogger(__name__)


class LeituraIndisponivel(Exception):
    def __init__(self, mensagem, transitorio=False):
        super().__init__(mensagem)
        self.transitorio = transitorio


def analisar_cartao(imagem: Path, campos_revisao: list[str] | None = None,
                    client=None, model: str = GEMINI_MODEL) -> CartaoExtraido:
    prompt = PROMPT
    if campos_revisao:
        prompt += "\nReanalise com atenção estes campos: " + ", ".join(campos_revisao)
    return _analisar(imagem, CartaoExtraido, prompt, client, model)


def analisar_pagina(imagem: Path, client=None, model: str = GEMINI_MODEL) -> LeituraCartao:
    return _analisar(imagem, LeituraCartao, PROMPT_PAGINA, client, model)


def _analisar(imagem, schema, prompt, client, model):
    proprio = client is None
    try:
        from google.genai import types
        if proprio:
            chave = gemini_api_key()
            if not chave:
                raise LeituraIndisponivel("Configure GEMINI_API_KEY para usar a leitura por IA")
            from google import genai
            client = genai.Client(api_key=chave, http_options=types.HttpOptions(
                timeout=60000, retry_options=types.HttpRetryOptions(attempts=1)))
        LOG.info("Chamada à IA iniciada")
        resposta = client.models.generate_content(
            model=model,
            contents=[types.Part.from_bytes(data=imagem.read_bytes(), mime_type="image/png"), prompt],
            config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=schema),
        )
        if not resposta.text:
            raise ValueError("Resposta vazia")
        resultado = schema.model_validate_json(resposta.text)
        LOG.info("Chamada à IA finalizada")
        return resultado
    except LeituraIndisponivel as exc:
        LOG.warning("Leitura por IA indisponível: %s", exc)
        raise
    except (OSError, ValueError, ValidationError) as exc:
        LOG.error("Resposta da IA inválida: %s", type(exc).__name__)
        raise LeituraIndisponivel("A IA não retornou uma leitura válida. Tente novamente.") from exc
    except Exception as exc:
        codigo = getattr(exc, "code", None)
        transitorio = codigo in (408, 429, 500, 502, 503, 504) or "Timeout" in type(exc).__name__ or "Connect" in type(exc).__name__
        LOG.error("Falha na chamada à IA: tipo=%s código=%s transitório=%s", type(exc).__name__, codigo, transitorio)
        raise LeituraIndisponivel("Não foi possível contatar a IA. Verifique a conexão, chave e disponibilidade do modelo.",
                                  transitorio=transitorio) from exc
    finally:
        if proprio and client is not None:
            client.close()
