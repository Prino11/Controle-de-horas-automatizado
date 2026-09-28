# Conferência de cartão de ponto

Aplicativo local Tkinter para selecionar um scan, interpretar com Gemini, corrigir os horários e salvar a revisão em JSON. O cartão é **enviado à API externa do Google** ao clicar em **Analisar com IA** ou **Reanalisar campos**. Sem chave, a aplicação abre normalmente e permite preenchimento manual.

## Instalação (Windows)

Use o **mesmo Python** para instalar e executar. No ambiente mostrado, a partir da pasta externa do projeto:

```powershell
& C:\Python314\python.exe -m pip install -r .\Controle-de-horas-automatizado-main\requirements.txt
& C:\Python314\python.exe .\Controle-de-horas-automatizado-main\main.py
```

O pacote `PIL` é fornecido pela dependência `Pillow`. Instalar com outro `python` não o disponibiliza no Python 3.14.

Configure `GEMINI_API_KEY` como variável de ambiente ou copie `.env.example` para `.env` e preencha a chave. O modelo padrão é `gemini-2.5-flash`; pode ser alterado via `GEMINI_MODEL`. O arquivo `.env` não deve ser compartilhado.

## Uso

Dentro da pasta que contém `main.py`, execute `& C:\Python314\python.exe main.py`.

Selecione PNG/JPG/JPEG ou PDF de até quatro páginas. Você pode selecionar **os dois PDFs de `assets` ao mesmo tempo**, frente (`lado_a_cartao.pdf`) e verso (`Lado B cartão.pdf`). A janela de seleção abre nessa pasta. Os PDFs-modelo deitados são girados para leitura; os botões **Girar** permitem ajustar outros scans. As páginas e lados são reunidos em sequência para análise e preview. O terceiro par de colunas `ENT/SAI` e a coluna `EXTRA` são mantidos nas observações do dia, editáveis na tabela; os quatro primeiros horários alimentam o cálculo. Cada original é copiado sem modificação para `input/scans/`; uma cópia com contraste moderado é usada para análise. A imagem aparece com zoom e barras de rolagem. Corrija os campos em `HH:MM`, confira os indicadores e clique em **Confirmar cartão**. Erros de validação bloqueiam o salvamento; campos ainda incertos exigem confirmação explícita. Os resultados ficam em `data/processed/<id>.json` com leitura original e valores confirmados.

O CSV em `input/registros.csv` é apenas exemplo legado, agora no formato de quatro marcações. A exportação Excel existente não integra este fluxo.

## Testes

```powershell
& C:\Python314\python.exe -m pip install -r requirements-dev.txt
& C:\Python314\python.exe -m pytest -q
```

Os testes são locais e não fazem chamadas reais à API. Não há integração direta com scanner; selecione o arquivo gerado por ele.

## Logs de diagnóstico

O aplicativo grava automaticamente eventos de execução, importação, leitura por IA, salvamento e erros em `logs/aplicativo.log`, na pasta que contém `main.py`. O arquivo inclui data e hora, nível, thread e módulo de origem. Erros inesperados incluem o rastreamento da exceção. A pasta é criada na primeira execução e não é versionada.

Quando o arquivo atinge 2 MB, ele é rotacionado. São mantidos até cinco arquivos anteriores (`aplicativo.log.1` a `aplicativo.log.5`). Para acompanhar os eventos no PowerShell, execute `Get-Content .\logs\aplicativo.log -Wait -Tail 50` dentro da pasta do aplicativo.

O programa oculta o valor de `GEMINI_API_KEY` ao formatar os logs. Os logs ainda podem conter nomes de arquivos, caminhos locais e detalhes de erros; confira o conteúdo antes de compartilhá-lo.
