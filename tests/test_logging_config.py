import logging

from config import logging_config


def test_logs_persistem_rotacionam_e_ocultam_chave(tmp_path, monkeypatch):
    chave = "chave-secreta-de-teste"
    monkeypatch.setenv("GEMINI_API_KEY", chave)
    monkeypatch.setattr(logging_config, "MAX_LOG_BYTES", 450)
    raiz = logging.getLogger()
    handlers_anteriores = set(raiz.handlers)
    nivel_anterior = raiz.level
    try:
        destino = logging_config.configurar_logs(tmp_path)
        assert logging_config.configurar_logs(tmp_path) == destino
        assert len(set(raiz.handlers) - handlers_anteriores) == 2
        for numero in range(5):
            logging.getLogger("teste.log").info("Evento %s: %s %s", numero, "x" * 160, chave)
        try:
            raise RuntimeError("erro de teste")
        except RuntimeError:
            logging.getLogger("teste.log").exception("Falha registrada")
        for handler in raiz.handlers:
            handler.flush()
        arquivos = [destino, *tmp_path.glob("aplicativo.log.*")]
        conteudo = "\n".join(arquivo.read_text(encoding="utf-8") for arquivo in arquivos)
        assert destino.exists()
        assert len(arquivos) > 1
        assert "[CHAVE_OCULTA]" in conteudo
        assert chave not in conteudo
        assert "Traceback" in conteudo
        assert "Falha registrada" in conteudo
    finally:
        for handler in set(raiz.handlers) - handlers_anteriores:
            raiz.removeHandler(handler)
            handler.close()
        raiz.setLevel(nivel_anterior)
