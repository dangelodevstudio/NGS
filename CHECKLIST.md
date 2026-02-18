# Checklist de Aceite - PDF Template B (modelo.pdf)

Data da validação: 2026-02-12  
Arquivo validado: `laudo-etapa10.pdf`

## Etapa 9 — Capas (re-validação)

- [PASS] Página 1 sem rodapé.
  - Evidência: `/tmp/et10_p1.png` (sem bloco de profissionais no rodapé).
- [PASS] Última página institucional (página 8) sem rodapé.
  - Evidência: `/tmp/et10_p8.png` (apenas background institucional).
- [PASS] Sem sobreposição indevida nas capas.
  - Evidência: `/tmp/et10_p1.png`, `/tmp/et10_p8.png`.

## Etapa 10 — Checklist e evidências por página

- [PASS] Página 1 (capa inicial): OK.
- [PASS] Página 2 (dados + resultado principal + tabela + interpretação curta): OK.
- [PASS] Página 3 (interpretação expandida + achados adicionais + tabela VUS): OK.
- [PASS] Página 4 (genes analisados): OK.
- [PASS] Página 5 (ordem métricas/recomendações/notas + linha "Região alvo..."): OK.
- [PASS] Página 6 (metodologia e blocos institucionais do template): OK.
- [PASS] Página 7 (referências bibliográficas no miolo): OK.
- [PASS] Página 8 (capa final institucional): OK.

## Aceites globais

- [PASS] Capas sem rodapé e sem paginação adicional desenhada pelo renderer.
- [PASS] Páginas internas com rodapé contendo "Analista responsável".
- [PASS] Sem página interna vazia adicional (miolo encerra em "Página 6 de 6").
- [PASS] Sem truncamentos críticos nas áreas ajustadas (p2/p3/p5/p6).

## Observações

- Os PNGs de background (`laudo144_pg06.png` e `laudo144_pg07.png`) já embutem parte do conteúdo institucional (incluindo blocos e referências).  
  Por isso, o renderer mantém overlay somente de conteúdo dinâmico nesses pontos para evitar duplicação visual.

## Main Result Controls (2026-02-18)

- [PASS] `Zigosidade`, `Herança` e `Classificação` com select + fallback `Outro` no editor.
- [PASS] Compatibilidade com dados legados: valores fora da lista abrem em `Outro`.
- [PASS] `Condição` com fenótipo editável e OMIM fixo no editor.
- [PASS] Persistência mantém campos existentes em `Report.data` (`main_zygosity`, `main_inheritance`, `main_classification`, `main_condition`).
- [PASS] Legenda automática de herança adicionada na página 2 (preview HTML + PDF ReportLab).
- [PASS] VUS não alterado (escopo restrito ao resultado principal).
- [PASS] Testes automatizados de regra/contexto/update (`python manage.py test editor -v 2`).
- [PASS] Validação de render PDF (`pdftotext` página 2 com condição + legenda).
