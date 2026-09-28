import logging

from config.logging_config import configurar_logs

if __name__ == "__main__":
    try:
        arquivo_log = configurar_logs()
        logging.getLogger(__name__).info("Aplicativo iniciado; logs em %s", arquivo_log)
        from gui.app import AppPonto

        app = AppPonto()
        app.mainloop()
        logging.getLogger(__name__).info("Aplicativo encerrado")
    except Exception:
        logging.getLogger(__name__).exception("Falha fatal ao iniciar ou executar o aplicativo")
        raise
