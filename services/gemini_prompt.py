PROMPT = """Este documento é um cartão de ponto brasileiro. Leia a estrutura visual e percorra cada linha/dia.
O modelo do projeto pode ter frente verde (1ª quinzena, dias 1–15) e verso laranja
(2ª quinzena, dias 16–31). As imagens podem aparecer uma abaixo da outra.
Há até três pares de colunas ENT/SAI e uma coluna EXTRA. Mapeie apenas os dois primeiros
pares, na ordem visual, para entrada_manha, saida_manha, entrada_tarde e saida_tarde.
Não confunda a terceira dupla ou EXTRA com os quatro campos principais; se houver escrita
nessas colunas, descreva-a em observacoes do dia. Não misture linhas de dias distintos.
Identifique funcionário, mês e ano somente se visíveis. Para cada dia, transcreva entrada e saída
da manhã e entrada e saída da tarde exatamente como aparecem, no formato HH:MM.
Nunca substitua uma informação ilegível por uma informação provável.
Não complete por lógica, não use dias anteriores, não calcule horas e não invente marcações.
Para campo realmente sem marcação use valor null e status VAZIO; para escrita impossível de ler,
use valor null e status ILEGIVEL; para caracteres ambíguos use status INCERTO e uma observação.
Use CONFIRMADO apenas quando a escrita for clara. Retorne exclusivamente a estrutura JSON solicitada.
"""

PROMPT_PAGINA = """Você está analisando UMA página digitalizada de um cartão de ponto brasileiro.
Primeiro, determine o lado de forma automática analisando a marcação estampada no cartão:

- Se houver o número "1" estampado grande na página, trata-se inequivocamente do lado A (dias 1 a 15).
- Se houver o número "2" estampado grande na página, trata-se inequivocamente do lado B (dias 16 a 31).
  Priorize sempre os números estampados para preencher o campo `numero_lado`. Cabeçalhos como '1ª QUINZENA' ou '2ª QUINZENA' servem apenas como confirmação secundária.
  Não determine o lado somente pela cor. Se o número não estiver visível, houver dúvida ou o documento não for um cartão, use DESCONHECIDO e status_lado INCERTO/ILEGIVEL.
  Transcreva numero_lado e cabecalho_quinzena somente quando visíveis.

Leia matrícula como STRING, preservando zeros iniciais. Leia nome, mês e ano visíveis,
cada um com valor e status. O verso (lado B) pode não ter nome; não copie de outros cartões.
Nunca invente matrícula, nome, data ou horário. Nunca substitua uma informação ilegível
por uma informação provável. Use null + ILEGIVEL quando não conseguir ler, null + VAZIO
quando não existir marcação. Para dúvida parcial use INCERTO e não complete por lógica.
Percorra as linhas: primeiro par ENT/SAI = entrada_manha/saida_manha; segundo par
ENT/SAI = entrada_tarde/saida_tarde. Terceiro par e EXTRA ficam em observacoes do dia.
Horários são HH:MM ou null. Se o relógio imprimiu um prefixo de dia da semana junto ao
horário, separe apenas quando isso for claramente observável. Não use padrões de
outros dias para completar informações. Não calcule jornada de trabalho.
Retorne apenas a estrutura JSON solicitada. Informe os dias efetivamente observados,
sem criar linhas de outra quinzena. Preserve rasuras e ambiguidades nas observações.
"""
