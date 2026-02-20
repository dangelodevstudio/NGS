from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST, require_http_methods
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count
from django.contrib.auth.models import User
from datetime import datetime
import uuid
import os
import logging
import re
import textwrap
import json
import unicodedata
from urllib.parse import urlparse
from .models import Folder, Report
from .pdf_renderer import render_template_b_pdf

logger = logging.getLogger(__name__)


# Modelos de laudo e respectivos valores padrÃ£o
LAUDO_MODELOS = {
    "cancer_hereditario_144": {
        "label": "PAINEL NGS PARA CÂNCER HEREDITÁRIO - 144 GENES",
        "defaults": {
            "exam_name": "PAINEL NGS PARA CÂNCER HEREDITÁRIO - 144 GENES",
            "requester_name": "Dr(a). Fulana de Tal CRM - BR 8141",
            "main_gene": "TP53",
            "main_transcript": "NM_000546.5",
            "main_variant_c": "c.1010G>A",
            "main_variant_p": "p.(Arg337His)",
            "main_dbsnp": "rs121912664",
            "main_zygosity": "Heterozigose",
            "main_inheritance": "Autossômica dominante",
            "main_classification": "Patogênica",
            "main_condition": "Síndrome de Li-Fraumeni (OMIM:#151623)",
            "main_result_intro": (
                "Foi identificada uma variante clinicamente relevante no gene TP53."
            ),
            "interpretation_text": (
                "A variante c.1010G>A:p.(Arg337His) no gene TP53 é uma variante do tipo missense, causada pela "
                "substituição de uma guanina por uma adenina, resultando na troca do aminoácido arginina por histidina "
                "na posição 337 da proteína. De acordo com o banco de dados populacional gnomAD, que documenta dados "
                "de sequenciamento de exomas e genomas de indivíduos não aparentados de diversas populações, esta "
                "variante apresenta uma frequência alélica de aproximadamente 0,0003% na população geral. No ClinVar, "
                "que compila variantes genéticas presentes em indivíduos com diversas patologias, esta variante é "
                "classificada como patogênica (Variation ID: 12379), e está associada principalmente à síndrome de "
                "Li-Fraumeni, uma condição de predisposição hereditária ao câncer.\n\n"
                "A literatura científica contém diversos relatos da presença dessa variante em famílias brasileiras com "
                "histórico de câncer precoce e múltiplos tumores, sendo considerada uma mutação fundadora no Brasil. De "
                "acordo com o banco de dados PubMed, a variante c.1010G>A:p.(Arg337His) já foi reportada previamente "
                "em pacientes com câncer de mama, sarcomas, tumores adrenocorticais, leucemias e outros tumores "
                "relacionados à síndrome de Li-Fraumeni (PMID: 16494995, 10864200, 16033918, 21192060, 27714481, "
                "16494995, 19046423, 22455664, 27223487, entre outros).\n\n"
                "O gene TP53 codifica a proteína p53, um regulador central da resposta celular ao dano genético. Trata-se "
                "de um importante gene supressor tumoral que atua promovendo parada do ciclo celular, reparo do DNA "
                "ou apoptose em resposta a estresses celulares. Variantes patogênicas neste gene, como a c.1010G>A, "
                "comprometem sua função de vigilância genômica, aumentando o risco de desenvolvimento de múltiplos "
                "tipos de câncer ao longo da vida.\n\n"
                "Este teste identificou variante clinicamente relevante nos genes TP53, associada ao aumento do risco "
                "para o desenvolvimento de neoplasias. Trata-se de condições de herança autossômica dominante, o que "
                "implica um risco de 50% de transmissão dessas variantes para cada descendente, além da possibilidade de "
                "terem sido herdadas de um dos genitores, dado que a maioria dos casos é familiar.\n\n"
                "Diante da importância de reconhecer familiares potencialmente em risco e orientar adequadamente sobre "
                "as implicações dessas alterações, a critério médico, recomenda-se o aconselhamento genético para o(a) "
                "paciente e seus familiares, bem como a oferta de estratégias de rastreamento precoce e medidas de "
                "redução de risco quando indicadas."
            ),
            "interpretation_inheritance_mode": "none",
            "interpretation_obs": "",
            "main_table_mode": "variant",
            "main_variant_extra_rows_text": "",
            "main_cnv_rows_text": "",
            "vus_gene": "PTEN",
            "vus_transcript": "NM_000314.8",
            "vus_variant_c": "c.775C>T",
            "vus_variant_p": "(p.His259Tyr)",
            "vus_dbsnp": "rs2132277651",
            "vus_zygosity": "Heterozigose",
            "vus_inheritance": "Autossômica dominante",
            "vus_classification": "VUS",
            "additional_table_mode": "variant",
            "additional_variant_extra_rows_text": "",
            "additional_cnv_rows_text": "",
            "additional_findings_text": (
                "Foram identificada(s) uma ou mais variante(s) de significado incerto nos genes analisados. Pelo "
                "conhecimento atual não é possível definir a patogenicidade dessa(s) variante(s) abaixo. Portanto, "
                "recomenda-se que essas informações não sejam usadas para fundamentar decisões clínicas. Sugere-se, "
                "ainda, acompanhamento da literatura científica a respeito da(s) mesma(s)."
            ),
            "additional_findings_mode": "manual",
            "additional_findings_obs": "",
            "secondary_table_mode": "variant",
            "secondary_variant_rows_text": "",
            "secondary_cnv_rows_text": "",
            "secondary_findings_mode": "manual",
            "secondary_findings_text": "",
            "secondary_findings_obs": "",
            "metrics_mode": "panel",
            "metrics_coverage_mean": "656x",
            "metrics_coverage_50x": "99,99%",
            "metrics_coverage_base": "50x",
            "metrics_nuclear_base": "30x",
            "metrics_nuclear_percent": "90,42%",
            "metrics_mito_base": "100x",
            "metrics_mito_percent": "98,45%",
            "metrics_text": (
                "Cobertura média do painel: 350x; 98% das bases com cobertura ≥50x. "
                "Regiões com cobertura inferior foram avaliadas e não impactam a interpretação clínica principal."
            ),
            "recommendations_text": (
                "A critério médico, recomenda-se aconselhamento genético, rastreamento oncológico periódico "
                "conforme protocolos para portadores de variantes em genes e de predisposição a câncer e testagem dos "
                "familiares de primeiro grau, visando esclarecimento do status genético e definição de medidas "
                "preventivas e de vigilância adequadas."
            ),
            "recommendations_mode": "manual",
            "recommendations_obs": "",
            "notes_obs": "",
            "notes_text": (
                "A análise genômica por sequenciamento de nova geração (NGS) foi realizada com o objetivo de "
                "identificar variantes genéticas potencialmente associadas ao fenótipo investigado. Essa metodologia "
                "abrange as regiões codificantes e limites exon–intron dos genes avaliados, permitindo a detecção da "
                "maioria das variantes relacionadas a condições monogênicas.\n\n"
                "Os dados também foram analisados quanto à presença de grandes deleções e duplicações intragênicas "
                "(CNVs), com alta correlação em relação à técnica de MLPA, embora pequenas discrepâncias "
                "metodológicas possam ocorrer.\n\n"
                "Este resultado não exclui a possibilidade de alterações em regiões não avaliadas por esta metodologia, "
                "como expansões de repetição, variantes intrônicas profundas, rearranjos estruturais complexos ou "
                "condições de etiologia multifatorial, que não são plenamente detectáveis pelo NGS."
            ),
            "methodology_text": (
                "A amostra é submetida a processos de extração de DNA nuclear, fragmentação, indexação e captura com "
                "kit específico, seguidos de enriquecimento das regiões de interesse. O sequenciamento é realizado em "
                "equipamento Illumina, seguido por análise na plataforma Sophia DDM, contemplando a detecção de "
                "variantes pontuais, indels e alterações de número de cópias (CNVs). Os parâmetros mínimos de qualidade "
                "de análise são definidos por cobertura média >20x e ≥90% das bases. O alinhamento é realizado contra o "
                "genoma de referência GRCh38/hg38 (nuclear). A anotação das variantes segue as recomendações da "
                "Human Genome Variation Society (HGVS) e a classificação é realizada de acordo com os critérios do "
                "American College of Medical Genetics and Genomics (ACMG), em consonância com as atualizações do "
                "workgroup do ClinGen."
            ),
            "methodology_mode": "manual",
            "limitations_text": (
                "Este exame não avalia regiões não codificantes do genoma, não sendo indicado para a investigação de "
                "condições associadas a expansões de polinucleotídeos ou para a detecção de eventos genéticos "
                "complexos, tais como inversões, translocações e expansões repetitivas. A presença de pseudogenes, "
                "sequências altamente homólogas ou regiões ricas em repetições pode interferir na análise e impactar a "
                "detecção de variantes genômicas. A análise de variações no número de cópias (CNVs) contempla "
                "alterações que envolvem três ou mais éxons do genoma nuclear. Para CNVs, não são descritas as "
                "coordenadas exatas dos pontos de quebra, e a acurácia na detecção pode ser influenciada pela "
                "quantidade e qualidade do DNA disponível na amostra biológica. Este exame apresenta sensibilidade "
                "superior a 99% para detecção de variantes do tipo SNV e pequenas inserções/deleções de até 20 pb. "
                "Alterações maiores que 20 pb e menores que um éxon podem ser detectadas com sensibilidade reduzida. "
                "A análise de CNVs que envolvem um ou mais éxons apresenta sensibilidade superior a 90%."
            ),
            "observations_text": (
                "A interpretação deste exame depende da correlação com dados clínicos e laboratoriais do(a) paciente. "
                "Exames genéticos não constituem, isoladamente, ferramenta definitiva para diagnóstico, devendo integrar "
                "o conjunto de informações utilizado pelo médico responsável. Este laudo reflete o conhecimento científico "
                "atual e pode ser atualizado conforme novos avanços. Variantes benignas, provavelmente benignas, "
                "intrônicas e sinônimas sem evidência de patogenicidade não são reportadas.\n\n"
                "A ausência de variantes patogênicas ou provavelmente patogênicas não exclui causa genética para o "
                "fenótipo. Resultados podem ser influenciados por limitações técnicas, variantes raras, contaminação ou "
                "situações clínicas específicas, como transplante de medula óssea de doador alogênico. No caso de "
                "variantes de significado clínico incerto (VUS), estas não devem, isoladamente, direcionar condutas "
                "médicas, nem justificar investigação em familiares fora de centros de pesquisa. Recomenda-se "
                "reavaliação futura conforme novas evidências.\n\n"
                "Quando identificadas variantes provavelmente patogênicas, sugere-se aconselhamento genético. Achados "
                "incidentais são reportados de acordo com as recomendações do ACMG. O arquivo de chamada de variantes "
                "(.vcf) encontra-se disponível mediante solicitação formal. Este exame foi validado internamente pela "
                "Bioma Genetics®."
            ),
            "genes_analyzed_list": (
                "AIP, ALK, APC, ATM, ATR, AXIN2, BAP1, BARD1, BLM, BMPR1A, BRCA1, BRCA2, BRIP1, BUB1B, CASR, "
                "CDC73, CDH1, CDK4, CDKN1B, CDKN1C, CDKN2A, CEBPA, CEP57, CHEK2, CTC1, CTNNA1, CYLD, "
                "DDB2, DICER1, DIS3L2, DKC1, EGFR, EGLN1, EPCAM, ERCC1, ERCC2, ERCC3, ERCC4, ERCC5, EXT1, "
                "EXT2, EZH2, FAN1, FANCA, FANCB, FANCC, FANCD2, FANCE, FANCF, FANCG, FANCI, FANCL, FANCM, "
                "FH, FLCN, GAA, GALNT12, GATA2, GBA, GLA, GPC3, GREM1, HDAC2, HNF1A, HOXB13, HRAS, IDUA, "
                "KIF1B, KIT, KMT2D, LZTR1, MAX, MC1R, MDH2, MEN1, MERTK, MET, MITF, MLH1, MLH3, MRE11, MSH2, "
                "MSH3, MSH6, MUTYH, NBN, NF1, NF2, NHP2, NOP10, NSD1, NTHL1, PALB2, PDGFRA, PHOX2B, PMS1, "
                "PMS2, PMS2CL, POLD1, POLE, POLH, POT1, PRF1, PRKAR1A, PRSS1, PTCH1, PTCH2, PTEN, RAD50, "
                "RAD51C, RAD51D, RB1, RECQL4, RET, RHBDF2, RUNX1, SBDS, SDHA, SDHAF2, SDHB, SDHC, SDHD, "
                "SLX4, SMAD4, SMARCA4, SMARCB1, SMARCE1, STK11, SUFU, TERC, TERT, TINF2, TMEM127, TP53, "
                "TSC1, TSC2, TYR, VHL, WRAP53, WRN, WT1, XPA, XPC e XRCC2 (144)"
            ),
            "references_text": (
                "Abou Tayoun NA, et al. Recommendations for interpreting the loss of function PVS1 ACMG/AMP variant "
                "criterion. Hum Mutat. 2018;39(11):1517-1524. doi:10.1002/humu.23626. PMID:30192042; PMCID:PMC6185798.\n"
                "Gudmundsson S, et al. Variant interpretation using population databases: Lessons from gnomAD. Hum "
                "Mutat. 2022;43(8):1012-1030.\n"
                "Illumina, Inc. Illumina DRAGEN Bio-IT Platform v3.6 User Guide (1000000128306 v00).\n"
                "Kopanos C, et al. VarSome: the human genomic variant search engine. Bioinformatics. 2019;35(11):1978-1980.\n"
                "Landrum MJ, et al. ClinVar: public archive of relationships among sequence variation and human phenotype. "
                "Nucleic Acids Res. 2014;42(Database issue):D980-D985.\n"
                "Li H, et al. The Sequence Alignment/Map format and SAMtools. Bioinformatics. 2009;25(16):2078-2079.\n"
                "Sociedade Brasileira de Patologia Clínica. Lista de orientação em Diagnóstico Molecular. 2ª versão. "
                "2018. Disponível em: http://www.sbpc.org.br\n"
                "MacArthur DG, et al. Guidelines for investigating causality of sequence variants in human disease. "
                "Nature. 2014;508(7497):469-476. doi:10.1038/nature13127.\n"
                "McKenna A, et al. The Genome Analysis Toolkit: a MapReduce framework for analyzing next-generation DNA "
                "sequencing data. Genome Res. 2010;20(9):1297-1303.\n"
                "Meyer LR, et al. The UCSC Genome Browser database: extensions and updates 2013. Nucleic Acids Res. "
                "2013;41(D1):D64-D69.\n"
                "Miller DT, et al. ACMG SF v3.2 list for reporting of secondary findings in clinical exome and genome "
                "sequencing: a policy statement of the ACMG. Genet Med. 2023;100866. doi:10.1016/j.gim.2023.100866.\n"
                "Richards S, et al. Standards and guidelines for the interpretation of sequence variants: a joint "
                "consensus recommendation of the ACMG and AMP. Genet Med. 2015;17(5):405-424.\n"
                "Riggs ER, et al. Technical standards for the interpretation and reporting of constitutional copy-number "
                "variants: a joint consensus recommendation of the ACMG and ClinGen. Genet Med. 2020;22(2):245-257.\n"
                "Sherry ST, et al. dbSNP: the NCBI database of genetic variation. Nucleic Acids Res. 2001;29(1):308-311."
            ),
            "analyst_name": "Analista Responsavel",
            "analyst_registry": "",
            "lab_tech_name": "Erika Macedo",
            "lab_tech_registry": "CRBM-SP: 26338",
            "geneticist_name": "Dr. Guilherme Lugo",
            "geneticist_registry": "CRM-SP: 256188",
            "director_name": "Dra. Ângela F. L. Waitzberg",
            "director_registry": "CRM-SP: 69504",
        },
    },
    # No futuro vamos adicionar mais modelos aqui (epilepsia, neuro, etc.)
}

REPORT_FIELDS = [
    "laudo_type",
    "patient_name",
    "patient_birth_date",
    "patient_sex",
    "patient_code",
    "exam_name",
    "exam_entry_date",
    "exam_release_date",
    "requester_name",
    "requester_reg_type",
    "requester_reg_type_other",
    "requester_reg_number",
    "requester_reg_state",
    "requester_not_identified",
    "sample_type",
    "sample_type_other",
    "sample_identifier",
    "sample_description",
    "clinical_indication",
    "main_gene",
    "main_transcript",
    "main_variant_c",
    "main_variant_p",
    "main_dbsnp",
    "main_zygosity",
    "main_inheritance",
    "main_classification",
    "main_condition",
    "main_result_intro",
    "interpretation_text",
    "interpretation_inheritance_mode",
    "interpretation_obs",
    "main_table_mode",
    "main_variant_extra_rows_text",
    "main_cnv_rows_text",
    "additional_findings_text",
    "additional_findings_mode",
    "additional_findings_obs",
    "additional_table_mode",
    "additional_variant_extra_rows_text",
    "additional_cnv_rows_text",
    "secondary_findings_mode",
    "secondary_findings_text",
    "secondary_findings_obs",
    "secondary_table_mode",
    "secondary_variant_rows_text",
    "secondary_cnv_rows_text",
    "vus_gene",
    "vus_transcript",
    "vus_variant_c",
    "vus_variant_p",
    "vus_dbsnp",
    "vus_zygosity",
    "vus_inheritance",
    "vus_classification",
    "metrics_coverage_mean",
    "metrics_coverage_50x",
    "metrics_coverage_base",
    "metrics_mode",
    "metrics_nuclear_base",
    "metrics_nuclear_percent",
    "metrics_mito_base",
    "metrics_mito_percent",
    "metrics_text",
    "recommendations_text",
    "recommendations_mode",
    "recommendations_obs",
    "notes_obs",
    "notes_text",
    "methodology_mode",
    "methodology_text",
    "limitations_text",
    "observations_text",
    "genes_analyzed_list",
    "references_text",
    "analyst_name",
    "analyst_registry",
    "lab_tech_name",
    "lab_tech_registry",
    "geneticist_name",
    "geneticist_registry",
    "director_name",
    "director_registry",
    "tech_professional",
    "tech_professional_crbm",
    "md_responsible",
    "md_responsible_crm",
    "md_technical",
    "md_technical_crm",
]

DEFAULT_REPORT_TITLE = "Novo laudo"
PLACEHOLDER_PATIENT_NAME = "NOME COMPLETO PACIENTE"

REQUESTER_REG_TYPES = [
    "CRM",
    "CRBio",
    "CRBM",
    "COREN",
    "CRF",
    "CPF",
    "Outro",
]

REQUESTER_UF_LIST = [
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS",
    "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC",
    "SP", "SE", "TO",
]


SAMPLE_TYPES = [
    "Swab bucal",
    "Sangue EDTA",
    "Liquido Amniotico",
    "Trofoblasto",
    "Sangue Fetal (Cordocentese)",
    "Biopsia de pele",
    "DNA extraido e enviado ao laboratorio",
    "Outro",
]

MAIN_ZYGOSITY_OPTIONS = [
    "Heterozigose",
    "Homozigose",
    "Hemizigose",
    "Outro",
]

MAIN_INHERITANCE_OPTIONS = [
    "Autossômica dominante",
    "Autossômica recessiva",
    "Ligada ao X dominante",
    "Ligada ao X recessiva",
    "Autossômica dominante/recessiva",
    "Mitocondrial",
    "Y-ligada",
    "Outro",
]

MAIN_CLASSIFICATION_OPTIONS = [
    "Patogênica",
    "Provavelmente patogênica",
    "VUS",
    "Alelo de risco",
    "Patogênica (em haplótipo)",
    "Provavelmente patogênica (em haplótipo)",
    "Outro",
]

MAIN_CONDITION_DEFAULT_OMIM = "151623"

PROFESSIONAL_OPTIONS = {
    "analyst": [
        {
            "name": "Analista Responsavel",
            "registry": "",
            "label": "Analista Responsavel",
        },
    ],
    "lab_tech": [
        {
            "name": "Erika Macedo",
            "registry": "CRBM-SP: 26338",
            "label": "Erika Macedo (CRBM-SP: 26338)",
        },
    ],
    "geneticist": [
        {
            "name": "Dr. Guilherme Lugo",
            "registry": "CRM-SP: 256188",
            "label": "Dr. Guilherme Lugo (CRM-SP: 256188)",
        },
    ],
    "director": [
        {
            "name": "Dra. Ângela F. L. Waitzberg",
            "registry": "CRM-SP: 69504",
            "label": "Dra. Ângela F. L. Waitzberg (CRM-SP: 69504)",
        },
    ],
}


TEXT_RULE_TOKEN_MAP = {
    "@AD": (
        "O modelo de herança observado é autossômico dominante. Dessa forma, o risco de recorrência para cada "
        "filho(a) do(a) indivíduo afetado(a) é de 50%, independentemente do sexo."
    ),
    "@AR": (
        "O modelo de herança observado é autossômico recessivo. Indivíduos afetados apresentam variantes "
        "patogênicas em ambos os alelos do gene. Quando ambos os genitores são portadores, o risco de recorrência "
        "para cada gestação é de 25% para filhos afetados, 50% para portadores assintomáticos e 25% para não portadores."
    ),
    "@LXR": (
        "O modelo de herança observado é ligado ao cromossomo X, recessivo. Mulheres portadoras apresentam risco "
        "de 50% de transmitir a variante a cada gestação, com possibilidade de filhos do sexo masculino afetados e "
        "filhas portadoras. Homens afetados transmitem a variante a todas as filhas, que serão portadoras, e a nenhum "
        "filho do sexo masculino."
    ),
    "@LX": (
        "O modelo de herança observado é ligado ao cromossomo X. A expressão clínica pode variar conforme o sexo e "
        "o padrão de dominância/recessividade associado à condição."
    ),
    "@LXD": (
        "O modelo de herança observado é ligado ao cromossomo X, dominante. Indivíduos do sexo feminino afetados "
        "apresentam risco de 50% de transmissão da variante a cada filho(a). Indivíduos do sexo masculino afetados "
        "transmitem a variante a todas as filhas e a nenhum filho do sexo masculino."
    ),
    "@LY": (
        "O modelo de herança observado é ligado ao cromossomo Y. A variante é transmitida exclusivamente de pai para "
        "filho do sexo masculino, com risco de recorrência de 100% para os filhos homens."
    ),
    "@HM": (
        "O modelo de herança observado é mitocondrial. A transmissão ocorre exclusivamente pela linhagem materna, "
        "sendo que todos os filhos de uma mulher portadora podem herdar a variante, enquanto indivíduos do sexo "
        "masculino não transmitem a condição aos seus descendentes."
    ),
    "@DENOVO": (
        "A variante identificada é considerada de novo, não tendo sido herdada dos genitores. Nesses casos, o risco "
        "de recorrência para futuras gestações é baixo, porém não nulo, devido à possibilidade de mosaicismo germinativo."
    ),
    "@PE": (
        "Embora o padrão de herança seja conhecido, a condição pode apresentar penetrância incompleta e/ou "
        "expressividade variável, o que significa que nem todos os indivíduos portadores da variante manifestarão "
        "sinais clínicos, ou poderão apresentá-los com intensidade variável."
    ),
}

INHERITANCE_TO_TOKEN = {
    "autossomica dominante": "@AD",
    "autossomico dominante": "@AD",
    "ad": "@AD",
    "autossomica recessiva": "@AR",
    "autossomico recessivo": "@AR",
    "ar": "@AR",
    "ligada ao x dominante": "@LXD",
    "ligado ao x dominante": "@LXD",
    "lxd": "@LXD",
    "ligada ao x recessiva": "@LXR",
    "ligado ao x recessivo": "@LXR",
    "lxr": "@LXR",
    "ligada ao x": "@LX",
    "ligado ao x": "@LX",
    "lx": "@LX",
    "mitocondrial": "@HM",
    "heranca mitocondrial": "@HM",
    "hm": "@HM",
    "y-ligada": "@LY",
    "ligada ao y": "@LY",
    "ligado ao y": "@LY",
    "holandrica": "@LY",
    "ly": "@LY",
}

INTERPRETATION_INHERITANCE_MODE_OPTIONS = [
    ("none", "Nao incluir automaticamente"),
    ("auto", "Incluir pela heranca da tabela"),
]

ADDITIONAL_FINDINGS_MODE_OPTIONS = [
    ("manual", "Manual"),
    ("vus", "Presenca de VUS"),
    ("vp_heterozygous", "Presenca de VP em heterozigose"),
    ("none", "Ausencia de achados adicionais"),
]

ADDITIONAL_FINDINGS_MODE_TEXT = {
    "vus": (
        "Foram identificada(s) uma ou mais variante(s) de significado incerto nos genes analisados. Pelo "
        "conhecimento atual nao e possivel definir a patogenicidade dessa(s) variante(s) abaixo. Portanto, "
        "recomenda-se que essas informacoes nao sejam usadas para fundamentar decisoes clinicas. Sugere-se, ainda, "
        "acompanhamento da literatura cientifica a respeito da(s) mesma(s)."
    ),
    "vp_heterozygous": (
        "Adicionalmente foram identificada(s) uma ou mais variante(s) patogenica(s) ou provavelmente patogenica(s), "
        "em heterozigose, em genes associados a condicoes de heranca autossomica recessiva. A presenca dessas "
        "variantes confere status de portador para o individuo analisado, nao estando associada, isoladamente, ao "
        "desenvolvimento da doenca. Recomenda-se aconselhamento genetico aos genitores e familiares, visando "
        "orientacao reprodutiva e adequada interpretacao desses achados."
    ),
    "none": (
        "Nao foram identificados achados adicionais clinicos relevantes. Nao foram observadas variantes de "
        "significado incerto (VUS), nem variantes patogenicas ou provavelmente patogenicas associadas a condicoes "
        "autossomicas recessivas em heterozigose."
    ),
}

SECONDARY_FINDINGS_MODE_OPTIONS = [
    ("manual", "Manual"),
    ("none", "Ausencia de achados secundarios"),
    ("present", "Presenca de achados secundarios"),
]

SECONDARY_FINDINGS_MODE_TEXT = {
    "none": (
        "Nao foram identificados achados secundarios conforme as recomendacoes da ACMG. Nenhuma variante patogenica "
        "ou provavelmente patogenica foi encontrada nos genes incluidos na lista de achados secundarios acionaveis e "
        "de reporte obrigatorio definida pela ACMG (American College of Medical Genetics and Genomics)."
    ),
    "present": (
        "Foram identificadas uma ou mais variantes clinicamente acionaveis em genes incluidos na lista de achados "
        "secundarios de reporte obrigatorio, conforme as recomendacoes vigentes do American College of Medical "
        "Genetics and Genomics (ACMG)."
    ),
}

RECOMMENDATIONS_MODE_OPTIONS = [
    ("manual", "Manual"),
    ("with_main_finding", "Presenca de achado principal"),
    ("without_main_finding", "Ausencia de achado principal"),
]

RECOMMENDATIONS_MODE_TEXT = {
    "with_main_finding": (
        "Os achados devem ser interpretados em correlacao com os dados clinicos e laboratoriais, podendo-se "
        "considerar, a criterio medico, a realizacao de testes complementares, como MLPA, sequenciamento de RNA ou "
        "sequenciamento genomico completo (WGS), ou genotipagem do genitores conforme a hipotese clinica. "
        "Ressalta-se que a interpretacao baseia-se no conhecimento cientifico atual e pode ser revisada a medida que "
        "novos dados se tornem disponiveis."
    ),
    "without_main_finding": (
        "Os achados devem ser interpretados em correlacao com os dados clinicos e laboratoriais, podendo-se "
        "considerar, a criterio medico, a realizacao de exames complementares como MLPA, PCR direcionado, "
        "microarranjo genomico (array-CGH ou SNP-array), sequenciamento genomico completo (WGS) ou tecnicas "
        "citogeneticas (FISH ou cariotipo), conforme a hipotese clinica. Recomenda-se, ainda, aconselhamento "
        "genetico para interpretacao conjunta dos achados, avaliacao de familiares potencialmente em risco e "
        "orientacoes reprodutivas, quando aplicavel."
    ),
}

METHODOLOGY_MODE_OPTIONS = [
    ("manual", "Manual"),
    ("panel", "Paineis"),
    ("exome_mito", "Exoma e paineis com genes mitocondriais"),
]

METHODOLOGY_MODE_TEXT = {
    "panel": (
        "A amostra e submetida a processos de extracao de DNA nuclear, fragmentacao, indexacao e captura com kit "
        "especifico, seguidos de enriquecimento das regioes de interesse. O sequenciamento e realizado em equipamento "
        "Illumina, seguido por analise na plataforma Sophia DDM, contemplando a deteccao de variantes pontuais, "
        "indels e alteracoes de numero de copias (CNVs). Os parametros minimos de qualidade de analise sao definidos "
        "por cobertura media >20x e >=90% das bases. O alinhamento e realizado contra o genoma de referencia "
        "GRCh38/hg38 (nuclear). A anotacao das variantes segue as recomendacoes da Human Genome Variation Society "
        "(HGVS) e a classificacao e realizada de acordo com os criterios do American College of Medical Genetics and "
        "Genomics (ACMG), em consonancia com as atualizacoes do workgroup do ClinGen."
    ),
    "exome_mito": (
        "A amostra e submetida a processos de extracao de DNA nuclear e mitocondrial, fragmentacao, indexacao e "
        "captura com kit especifico, seguidos de enriquecimento das regioes de interesse. O sequenciamento e realizado "
        "em equipamento Illumina, seguido por analise na plataforma Sophia DDM, contemplando a deteccao de variantes "
        "pontuais, indels e alteracoes de numero de copias (CNVs). Os parametros minimos de qualidade de analise sao "
        "definidos por cobertura media >20x e >=90% das bases. O alinhamento e realizado contra o genoma de "
        "referencia GRCh38/hg38 (nuclear) e NC_012920/rCRS (mitocondrial). A anotacao das variantes segue as "
        "recomendacoes da Human Genome Variation Society (HGVS) e a classificacao e realizada de acordo com os "
        "criterios do American College of Medical Genetics and Genomics (ACMG), em consonancia com as atualizacoes "
        "do workgroup do ClinGen."
    ),
}

TABLE_MODE_OPTIONS = [
    ("variant", "Variantes SNV/indel"),
    ("cnv", "CNV (delecao/duplicacao)"),
]

METRICS_MODE_OPTIONS = [
    ("panel", "Paineis"),
    ("exome_mito", "Exoma e paineis com genes mitocondriais"),
]

VARIANT_LINE_FIELDS = [
    "gene",
    "transcript",
    "variant_c",
    "variant_p",
    "dbsnp",
    "zygosity",
    "inheritance",
    "classification",
    "condition",
]

CNV_LINE_FIELDS = [
    "cnv_type",
    "coordinate",
    "region",
    "zygosity",
    "classification",
]


def _get_report_type_options():
    return [{"key": key, "label": value["label"]} for key, value in LAUDO_MODELOS.items()]


def _resolve_laudo_type(request, base_data=None):
    return (
        request.POST.get("laudo_type")
        or (base_data or {}).get("laudo_type")
        or "cancer_hereditario_144"
    )


def _get_exam_name_for_type(laudo_type):
    model = LAUDO_MODELOS.get(laudo_type) or LAUDO_MODELOS["cancer_hereditario_144"]
    return model.get("label", "")


def _to_bool(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).lower() in ("1", "true", "on", "yes")


def _normalize_date_ddmmyyyy(value):
    text = (value or "").strip()
    if not text:
        return "00/00/0000"
    if text == "00/00/0000":
        return text

    text = text.replace("-", "/").replace(".", "/")
    if re.match(r"^\d{8}$", text):
        text = f"{text[:2]}/{text[2:4]}/{text[4:]}"
    if not re.match(r"^\d{2}/\d{2}/\d{4}$", text):
        return "00/00/0000"
    try:
        datetime.strptime(text, "%d/%m/%Y")
    except ValueError:
        return "00/00/0000"
    return text


def _normalize_main_dates(data):
    for field in ["patient_birth_date", "exam_entry_date", "exam_release_date"]:
        data[field] = _normalize_date_ddmmyyyy(data.get(field))
    return data


def _normalize_metrics_base(value):
    raw = (value or "").strip()
    if not raw:
        return "50x"
    compact = re.sub(r"\s+", "", raw)
    if re.fullmatch(r"\d+", compact):
        return f"{compact}x"
    if re.fullmatch(r"\d+x", compact, flags=re.IGNORECASE):
        return f"{compact[:-1]}x"
    return raw


def _normalize_table_mode(value):
    mode = (value or "variant").strip().lower()
    return mode if mode in {"variant", "cnv"} else "variant"


def _split_table_line(line):
    raw = (line or "").strip()
    if not raw:
        return []
    if ";" in raw:
        parts = raw.split(";")
    elif "|" in raw:
        parts = raw.split("|")
    else:
        parts = [raw]
    return [part.strip() for part in parts]


def _parse_rows_text(value, fields):
    text = str(value or "")
    if not text.strip():
        return []

    rows = []
    for line in text.splitlines():
        if not line.strip():
            continue
        parts = _split_table_line(line)
        if not parts:
            continue
        if len(parts) < len(fields):
            parts = parts + [""] * (len(fields) - len(parts))
        row = {field: parts[idx] if idx < len(parts) else "" for idx, field in enumerate(fields)}
        if any(row.values()):
            rows.append(row)
    return rows


def _rows_to_text(rows, fields):
    lines = []
    for row in rows or []:
        values = [str((row or {}).get(field, "") or "").strip() for field in fields]
        if any(values):
            lines.append("; ".join(values))
    return "\n".join(lines)


def _build_main_legacy_variant_row(data):
    row = {
        "gene": str(data.get("main_gene", "") or "").strip(),
        "transcript": str(data.get("main_transcript", "") or "").strip(),
        "variant_c": str(data.get("main_variant_c", "") or "").strip(),
        "variant_p": str(data.get("main_variant_p", "") or "").strip(),
        "dbsnp": str(data.get("main_dbsnp", "") or "").strip(),
        "zygosity": str(data.get("main_zygosity", "") or "").strip(),
        "inheritance": str(data.get("main_inheritance", "") or "").strip(),
        "classification": str(data.get("main_classification", "") or "").strip(),
        "condition": str(data.get("main_condition", "") or "").strip(),
    }
    return row if any(row.values()) else {}


def _build_additional_legacy_variant_row(data):
    row = {
        "gene": str(data.get("vus_gene", "") or "").strip(),
        "transcript": str(data.get("vus_transcript", "") or "").strip(),
        "variant_c": str(data.get("vus_variant_c", "") or "").strip(),
        "variant_p": str(data.get("vus_variant_p", "") or "").strip(),
        "dbsnp": str(data.get("vus_dbsnp", "") or "").strip(),
        "zygosity": str(data.get("vus_zygosity", "") or "").strip(),
        "inheritance": str(data.get("vus_inheritance", "") or "").strip(),
        "classification": str(data.get("vus_classification", "") or "").strip(),
        "condition": "",
    }
    return row if any(row.values()) else {}


def _build_rule_table_payload(data):
    main_mode = _normalize_table_mode(data.get("main_table_mode"))
    additional_mode = _normalize_table_mode(data.get("additional_table_mode"))
    secondary_mode = _normalize_table_mode(data.get("secondary_table_mode"))

    main_extra_variant_rows = _parse_rows_text(data.get("main_variant_extra_rows_text"), VARIANT_LINE_FIELDS)
    main_cnv_rows = _parse_rows_text(data.get("main_cnv_rows_text"), CNV_LINE_FIELDS)
    additional_extra_variant_rows = _parse_rows_text(data.get("additional_variant_extra_rows_text"), VARIANT_LINE_FIELDS)
    additional_cnv_rows = _parse_rows_text(data.get("additional_cnv_rows_text"), CNV_LINE_FIELDS)
    secondary_variant_rows = _parse_rows_text(data.get("secondary_variant_rows_text"), VARIANT_LINE_FIELDS)
    secondary_cnv_rows = _parse_rows_text(data.get("secondary_cnv_rows_text"), CNV_LINE_FIELDS)

    main_first = _build_main_legacy_variant_row(data)
    main_variant_rows = ([main_first] if main_first else []) + main_extra_variant_rows

    additional_first = _build_additional_legacy_variant_row(data)
    additional_variant_rows = ([additional_first] if additional_first else []) + additional_extra_variant_rows

    return {
        "main_table_mode": main_mode,
        "main_variant_rows": main_variant_rows,
        "main_cnv_rows": main_cnv_rows,
        "additional_table_mode": additional_mode,
        "additional_variant_rows": additional_variant_rows,
        "additional_cnv_rows": additional_cnv_rows,
        "secondary_table_mode": secondary_mode,
        "secondary_variant_rows": secondary_variant_rows,
        "secondary_cnv_rows": secondary_cnv_rows,
        # normalized text for admin textarea persistence
        "main_variant_extra_rows_text": _rows_to_text(main_extra_variant_rows, VARIANT_LINE_FIELDS),
        "main_cnv_rows_text": _rows_to_text(main_cnv_rows, CNV_LINE_FIELDS),
        "additional_variant_extra_rows_text": _rows_to_text(additional_extra_variant_rows, VARIANT_LINE_FIELDS),
        "additional_cnv_rows_text": _rows_to_text(additional_cnv_rows, CNV_LINE_FIELDS),
        "secondary_variant_rows_text": _rows_to_text(secondary_variant_rows, VARIANT_LINE_FIELDS),
        "secondary_cnv_rows_text": _rows_to_text(secondary_cnv_rows, CNV_LINE_FIELDS),
    }


def _normalize_patient_name(value):
    return (value or "").strip().upper()


def _split_condition_omim(main_condition_str):
    text = (main_condition_str or "").strip()
    if not text:
        return "", MAIN_CONDITION_DEFAULT_OMIM

    pattern = re.compile(r"\(\s*OMIM\s*:\s*#?\s*([A-Za-z0-9.\-]+)\s*\)", re.IGNORECASE)
    match = pattern.search(text)
    if not match:
        return text, MAIN_CONDITION_DEFAULT_OMIM

    omim = _normalize_omim_number(match.group(1)) or MAIN_CONDITION_DEFAULT_OMIM
    phenotype = f"{text[:match.start()]} {text[match.end():]}".strip(" ,;:-")
    return phenotype, omim


def _normalize_omim_number(value):
    if value is None:
        return ""
    digits = re.sub(r"\D", "", str(value))
    return digits


def _compose_main_condition(phenotype, omim):
    normalized_phenotype = (phenotype or "").strip()
    if not normalized_phenotype:
        return ""

    normalized_omim = _normalize_omim_number(omim)
    if not normalized_omim:
        normalized_omim = MAIN_CONDITION_DEFAULT_OMIM
    return f"{normalized_phenotype} (OMIM:#{normalized_omim})"


def _resolve_select_value(stored_value, allowed_values):
    allowed = set(allowed_values)
    normalized = (stored_value or "").strip()
    if not normalized:
        return "", ""
    if normalized in allowed:
        return normalized, ""
    if normalized.lower() == "outro":
        return "Outro", ""
    return "Outro", normalized


def _resolve_select_post(request, choice_field, other_field, legacy_field, allowed_values):
    allowed = set(allowed_values)
    choice = (request.POST.get(choice_field) or "").strip()
    other = (request.POST.get(other_field) or "").strip()
    legacy = (request.POST.get(legacy_field) or "").strip()

    if choice:
        if choice == "Outro":
            return other or legacy
        if choice in allowed:
            return choice

    if legacy:
        return legacy
    return ""


def _build_inheritance_legend(inheritance_text):
    value = (inheritance_text or "").strip()
    if not value:
        return ""

    mapping = {
        "Autossômica dominante": "Modelo de herança: autossômica dominante (AD).",
        "Autossômica recessiva": "Modelo de herança: autossômica recessiva (AR).",
        "Ligada ao X dominante": "Modelo de herança: ligada ao X dominante (XLD).",
        "Ligada ao X recessiva": "Modelo de herança: ligada ao X recessiva (XLR).",
        "Autossômica dominante/recessiva": "Modelo de herança: autossômica dominante/recessiva (AD/AR).",
        "Mitocondrial": "Modelo de herança: mitocondrial (MT).",
        "Y-ligada": "Modelo de herança: ligada ao Y (Y-linked).",
    }
    return mapping.get(value, f"Modelo de herança: {value}.")


def _append_optional_obs(text, obs):
    base = (text or "").strip()
    note = (obs or "").strip()
    if not note:
        return base
    return f"{base}\n\n{note}".strip() if base else note


def _remove_trailing_paragraph_occurrences(text, paragraph):
    content = (text or "").strip()
    target = (paragraph or "").strip()
    if not content or not target:
        return content
    parts = [part.strip() for part in re.split(r"\n\s*\n", content) if part.strip()]
    while parts and parts[-1] == target:
        parts.pop()
    return "\n\n".join(parts)


def _remove_repeated_tail_paragraph(text):
    content = (text or "").strip()
    if not content:
        return content
    parts = [part.strip() for part in re.split(r"\n\s*\n", content) if part.strip()]
    if len(parts) < 2 or parts[-1] != parts[-2]:
        return content
    tail = parts[-1]
    while parts and parts[-1] == tail:
        parts.pop()
    return "\n\n".join(parts)


def _replace_text_rule_tokens(text):
    rendered = str(text or "")
    for token, paragraph in TEXT_RULE_TOKEN_MAP.items():
        rendered = re.sub(re.escape(token), paragraph, rendered, flags=re.IGNORECASE)
    return rendered


def _build_table_token_map(data):
    table_payload = _build_rule_table_payload(data)
    main_rows = table_payload.get("main_variant_rows", [])
    additional_rows = table_payload.get("additional_variant_rows", [])

    row1 = main_rows[0] if len(main_rows) > 0 else {}
    row2 = main_rows[1] if len(main_rows) > 1 else {}
    add_row1 = additional_rows[0] if len(additional_rows) > 0 else {}

    def _v(row, key, fallback=""):
        return str((row or {}).get(key, "") or fallback or "").strip()

    return {
        "@GENE": _v(row1, "gene", data.get("main_gene", "")),
        "@TRANSCRITO": _v(row1, "transcript", data.get("main_transcript", "")),
        "@VAR_C": _v(row1, "variant_c", data.get("main_variant_c", "")),
        "@VAR_P": _v(row1, "variant_p", data.get("main_variant_p", "")),
        "@DBSNP": _v(row1, "dbsnp", data.get("main_dbsnp", "")),
        "@ZIGOSIDADE": _v(row1, "zygosity", data.get("main_zygosity", "")),
        "@HERANCA": _v(row1, "inheritance", data.get("main_inheritance", "")),
        "@CLASSIFICACAO": _v(row1, "classification", data.get("main_classification", "")),
        "@CONDICAO": _v(row1, "condition", data.get("main_condition", "")),
        "@GENE2": _v(row2, "gene"),
        "@TRANSCRITO2": _v(row2, "transcript"),
        "@VAR_C2": _v(row2, "variant_c"),
        "@VAR_P2": _v(row2, "variant_p"),
        "@DBSNP2": _v(row2, "dbsnp"),
        "@ZIGOSIDADE2": _v(row2, "zygosity"),
        "@HERANCA2": _v(row2, "inheritance"),
        "@CLASSIFICACAO2": _v(row2, "classification"),
        "@CONDICAO2": _v(row2, "condition"),
        "@VUS_GENE": _v(add_row1, "gene", data.get("vus_gene", "")),
        "@VUS_TRANSCRITO": _v(add_row1, "transcript", data.get("vus_transcript", "")),
        "@VUS_VAR_C": _v(add_row1, "variant_c", data.get("vus_variant_c", "")),
        "@VUS_VAR_P": _v(add_row1, "variant_p", data.get("vus_variant_p", "")),
        "@VUS_DBSNP": _v(add_row1, "dbsnp", data.get("vus_dbsnp", "")),
        "@VUS_ZIGOSIDADE": _v(add_row1, "zygosity", data.get("vus_zygosity", "")),
        "@VUS_HERANCA": _v(add_row1, "inheritance", data.get("vus_inheritance", "")),
        "@VUS_CLASSIFICACAO": _v(add_row1, "classification", data.get("vus_classification", "")),
    }


def _replace_table_tokens(text, data):
    rendered = str(text or "")
    token_items = sorted(_build_table_token_map(data).items(), key=lambda item: len(item[0]), reverse=True)
    for token, value in token_items:
        rendered = re.sub(re.escape(token), value, rendered, flags=re.IGNORECASE)
    return rendered


def _resolve_inheritance_paragraph(inheritance_text):
    normalized = _normalize_lookup_text(inheritance_text)
    if not normalized:
        return ""

    token = INHERITANCE_TO_TOKEN.get(normalized)
    if token:
        return TEXT_RULE_TOKEN_MAP.get(token, "")

    # Suporta combinações como "Autossômica dominante/recessiva".
    if "dominante/recessiva" in normalized or "dominante/recessivo" in normalized:
        parts = [TEXT_RULE_TOKEN_MAP.get("@AD", ""), TEXT_RULE_TOKEN_MAP.get("@AR", "")]
        return "\n\n".join([part for part in parts if part]).strip()

    combined_tokens = []
    for piece in re.split(r"[\/,;]|\se\s", normalized):
        token_piece = INHERITANCE_TO_TOKEN.get(piece.strip())
        if token_piece and token_piece not in combined_tokens:
            combined_tokens.append(token_piece)
    paragraphs = [TEXT_RULE_TOKEN_MAP.get(token_piece, "") for token_piece in combined_tokens]
    paragraphs = [paragraph for paragraph in paragraphs if paragraph]
    return "\n\n".join(paragraphs).strip()


def _normalize_lookup_text(value):
    text = str(value or "").strip().lower()
    if not text:
        return ""
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", text)


def _build_mode_options(raw_options):
    return [{"key": key, "label": label} for key, label in raw_options]


def _build_rule_based_texts(data):
    interpretation_mode = (data.get("interpretation_inheritance_mode") or "none").strip()
    table_payload = _build_rule_table_payload(data)
    first_main_row = table_payload.get("main_variant_rows", [{}])[0] if table_payload.get("main_variant_rows") else {}
    interpretation_text = _replace_table_tokens(data.get("interpretation_text", ""), data)
    interpretation_text = _replace_text_rule_tokens(interpretation_text)
    if interpretation_mode == "auto":
        inheritance_source = first_main_row.get("inheritance") or data.get("main_inheritance", "")
        inheritance_paragraph = _resolve_inheritance_paragraph(inheritance_source)
        if inheritance_paragraph and inheritance_paragraph not in interpretation_text:
            interpretation_text = f"{interpretation_text}\n\n{inheritance_paragraph}".strip()
    interpretation_rendered = _append_optional_obs(interpretation_text, data.get("interpretation_obs", ""))

    additional_mode = (data.get("additional_findings_mode") or "manual").strip()
    additional_text = data.get("additional_findings_text", "")
    if additional_mode in ADDITIONAL_FINDINGS_MODE_TEXT:
        additional_text = ADDITIONAL_FINDINGS_MODE_TEXT[additional_mode]
    additional_text = _replace_table_tokens(additional_text, data)
    additional_text = _replace_text_rule_tokens(additional_text)
    additional_rendered = _append_optional_obs(additional_text, data.get("additional_findings_obs", ""))

    secondary_mode = (data.get("secondary_findings_mode") or "manual").strip()
    secondary_text = data.get("secondary_findings_text", "")
    if secondary_mode in SECONDARY_FINDINGS_MODE_TEXT:
        secondary_text = SECONDARY_FINDINGS_MODE_TEXT[secondary_mode]
    secondary_text = _replace_table_tokens(secondary_text, data)
    secondary_text = _replace_text_rule_tokens(secondary_text)
    secondary_rendered = _append_optional_obs(secondary_text, data.get("secondary_findings_obs", ""))

    recommendations_mode = (data.get("recommendations_mode") or "manual").strip()
    recommendations_text = data.get("recommendations_text", "")
    if recommendations_mode in RECOMMENDATIONS_MODE_TEXT:
        recommendations_text = RECOMMENDATIONS_MODE_TEXT[recommendations_mode]
    recommendations_text = _replace_table_tokens(recommendations_text, data)
    recommendations_text = _replace_text_rule_tokens(recommendations_text)
    recommendations_rendered = _append_optional_obs(recommendations_text, data.get("recommendations_obs", ""))

    methodology_mode = (data.get("methodology_mode") or "manual").strip()
    methodology_text = data.get("methodology_text", "")
    if methodology_mode in METHODOLOGY_MODE_TEXT:
        methodology_text = METHODOLOGY_MODE_TEXT[methodology_mode]
    methodology_text = _replace_table_tokens(methodology_text, data)
    methodology_rendered = _replace_text_rule_tokens(methodology_text)

    notes_text = _replace_table_tokens(data.get("notes_text", ""), data)
    notes_text = _replace_text_rule_tokens(notes_text)
    notes_rendered = _append_optional_obs(notes_text, data.get("notes_obs", ""))

    return {
        "interpretation_text_rendered": interpretation_rendered,
        "additional_findings_text_rendered": additional_rendered,
        "secondary_findings_text_rendered": secondary_rendered,
        "recommendations_text_rendered": recommendations_rendered,
        "methodology_text_rendered": methodology_rendered,
        "notes_text_rendered": notes_rendered,
    }


def _strip_legacy_obs_from_text(data, previous_data, request, text_key, obs_key):
    if request.method != "POST":
        return
    if obs_key not in request.POST:
        return
    current_obs = (data.get(obs_key) or "").strip()
    if current_obs:
        return
    previous_obs = (previous_data.get(obs_key) or "").strip()
    if previous_obs:
        data[text_key] = _remove_trailing_paragraph_occurrences(data.get(text_key, ""), previous_obs)
        return
    data[text_key] = _remove_repeated_tail_paragraph(data.get(text_key, ""))


def _normalize_requester_name(value):
    text = (value or "").strip()
    if not text:
        return ""
    text = re.sub(r"^\s*dr(?:\(a\)|a)?\.?\s*", "", text, flags=re.IGNORECASE)
    text = text.lstrip(" -,:;.")
    return re.sub(r"\s+", " ", text).strip()


def _format_requester_display(data):
    if not data:
        return ""
    if _to_bool(data.get("requester_not_identified")):
        return "Nao identificado"

    name = _normalize_requester_name(data.get("requester_name"))
    reg_type = (data.get("requester_reg_type") or "").strip()
    reg_type_other = (data.get("requester_reg_type_other") or "").strip()
    reg_number = (data.get("requester_reg_number") or "").strip()
    reg_state = (data.get("requester_reg_state") or "").strip()

    if reg_type == "Outro":
        reg_type = reg_type_other

    has_reg = any([reg_type, reg_number, reg_state])

    if name and not has_reg:
        return f"Dr(a). {name}"

    parts = []
    if name:
        parts.append(f"Dr(a). {name}")
    elif has_reg:
        parts.append("Dr(a).")
    if reg_type:
        parts.append(reg_type)

    display = " ".join([p for p in parts if p]).strip()

    if reg_state:
        suffix = reg_state
        if reg_number:
            suffix = f"{suffix} {reg_number}"
        display = f"{display} - {suffix}" if display else suffix
    elif reg_number:
        display = f"{display} {reg_number}" if display else reg_number

    return display.strip()



def _parse_sample_description(description):
    if not description:
        return "", ""
    raw = description.strip()
    if "(" in raw and raw.endswith(")"):
        left = raw[: raw.rfind("(")].strip()
        right = raw[raw.rfind("(") + 1 : -1].strip()
        return left, right
    return raw, ""
def _format_sample_display(data):
    if not data:
        return ""
    sample_type = (data.get("sample_type") or "").strip()
    sample_other = (data.get("sample_type_other") or "").strip()
    sample_identifier = (data.get("sample_identifier") or "").strip()

    if sample_type == "Outro":
        sample_type = sample_other

    if not sample_type:
        return ""

    if sample_identifier:
        return f"{sample_type} ({sample_identifier})"
    return sample_type


def _split_text_by_lines(text, max_lines, max_chars):
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    lines_used = 0
    part1 = []
    part2 = []

    for index, para in enumerate(paragraphs):
        normalized = re.sub(r"\s+", " ", para)
        wrapped = textwrap.wrap(normalized, width=max_chars)
        if lines_used + len(wrapped) <= max_lines:
            part1.append(para)
            lines_used += len(wrapped)
            continue

        remaining = max_lines - lines_used
        if remaining > 0:
            part1.append(" ".join(wrapped[:remaining]))
            tail = wrapped[remaining:]
            if tail:
                part2.append(" ".join(tail))
        else:
            part2.append(para)
        part2.extend(paragraphs[index + 1 :])
        break

    return "\n\n".join(part1).strip(), "\n\n".join(part2).strip()


def _split_text_to_chunks(text, max_lines, max_chars_per_line):
    if not text:
        return []
    remaining = text.strip()
    if not remaining:
        return []
    chunks = []
    while remaining:
        part1, part2 = _split_text_by_lines(remaining, max_lines, max_chars_per_line)
        if part1:
            chunks.append(part1)
        remaining = part2.strip() if part2 else ""
    return chunks


def _split_interpretation_for_template_b(text, max_lines_p2=7, max_lines_p3=19, max_chars_per_line=96):
    """
    Divide o texto de interpretação pelo limite aproximado de linhas da caixa da página 2.
    Mantém parágrafos e evita abrir a página 3 sem necessidade.
    """
    if not text:
        return "", "", []
    cleaned = text.strip()
    if not cleaned:
        return "", "", []
    part1, remaining = _split_text_by_lines(cleaned, max_lines_p2, max_chars_per_line)
    part2, remaining = _split_text_by_lines(remaining, max_lines_p3, max_chars_per_line)
    overflow_chunks = _split_text_to_chunks(remaining, 34, max_chars_per_line)
    return part1, part2, overflow_chunks


def _split_text_with_overflow(text, first_lines, overflow_lines, max_chars_per_line=88):
    if not text:
        return "", []
    cleaned = text.strip()
    if not cleaned:
        return "", []
    part1, remaining = _split_text_by_lines(cleaned, first_lines, max_chars_per_line)
    overflow_chunks = _split_text_to_chunks(remaining, overflow_lines, max_chars_per_line)
    return part1, overflow_chunks


def _parse_layout_overflow(request):
    if request.method != "POST":
        return {}
    raw = request.POST.get("layout_overflow")
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _get_layout_section(layout, section):
    if not isinstance(layout, dict):
        return None
    value = layout.get(section)
    return value if isinstance(value, dict) else None


def _normalize_overflow_chunks(value):
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _normalize_text_for_layout(text):
    if not text:
        return ""
    if not isinstance(text, str):
        text = str(text)
    normalized = text.replace("\r\n", "\n").strip()
    if not normalized:
        return ""
    parts = re.split(r"\n\s*\n", normalized)
    cleaned = []
    for part in parts:
        line = re.sub(r"\s*\n\s*", " ", part.strip())
        line = re.sub(r"\s+", " ", line)
        if line:
            cleaned.append(line)
    return "\n\n".join(cleaned)

def _normalize_report_data(value, report_id=None):
    if isinstance(value, dict):
        return value
    if value is None:
        return {}
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            if report_id:
                logger.warning("Report %s has invalid JSON data; using empty data.", report_id)
            return {}
        if isinstance(parsed, dict):
            return parsed
        if report_id:
            logger.warning("Report %s data is not a JSON object; using empty data.", report_id)
        return {}
    if report_id:
        logger.warning("Report %s data has unexpected type %s; using empty data.", report_id, type(value).__name__)
    return {}



def _extract_report_data(request, base_data=None):
    data = {}
    source = _normalize_report_data(base_data)
    for field in REPORT_FIELDS:
        if field == "requester_not_identified":
            if request.method == "POST":
                data[field] = field in request.POST
            elif field in source:
                data[field] = _to_bool(source.get(field))
            continue
        if request.method == "POST" and field in request.POST:
            data[field] = request.POST.get(field, "")
        elif field in source:
            data[field] = source.get(field)
    if "laudo_type" not in data:
        data["laudo_type"] = _resolve_laudo_type(request, base_data)
    return data


def _build_context(request, base_data=None):
    base_data = _normalize_report_data(base_data)
    # tipo de laudo selecionado (default = câncer hereditário 144 genes)
    laudo_type = _resolve_laudo_type(request, base_data)
    modelo = LAUDO_MODELOS.get(laudo_type, LAUDO_MODELOS["cancer_hereditario_144"])
    defaults = modelo["defaults"]

    # helper para pegar valor do POST, dados salvos ou default
    def get_field(name, fallback=None):
        if fallback is None:
            fallback = defaults.get(name, "")
        if request.method == "POST" and name in request.POST:
            return request.POST.get(name, "")
        if base_data and name in base_data:
            return base_data.get(name)
        return fallback

    context = {
        # manter tipo de laudo no contexto (para o select e para a prévia)
        "laudo_type": laudo_type,

        # dados do paciente (sempre editáveis, com placeholders)
        "patient_name": get_field("patient_name", "NOME COMPLETO PACIENTE"),
        "patient_birth_date": get_field("patient_birth_date", "00/00/0000"),
        "patient_sex": get_field("patient_sex", "Masculino/Feminino"),
        "patient_code": get_field("patient_code", "0000000000"),
        "patient_birth_date_cover": get_field("patient_birth_date_cover", "00/00/000"),
        "patient_code_cover": get_field("patient_code_cover", "000000000000000"),

        # dados do exame
        "exam_name": _get_exam_name_for_type(laudo_type),
        "exam_entry_date": get_field("exam_entry_date", "00/00/0000"),
        "exam_release_date": get_field("exam_release_date", "00/00/0000"),

        # solicitante / amostra
        "requester_name": get_field("requester_name"),
        "requester_reg_type": get_field("requester_reg_type", ""),
        "requester_reg_type_other": get_field("requester_reg_type_other", ""),
        "requester_reg_number": get_field("requester_reg_number", ""),
        "requester_reg_state": get_field("requester_reg_state", ""),
        "requester_not_identified": get_field("requester_not_identified", False),
        "sample_type": get_field("sample_type", ""),
        "sample_type_other": get_field("sample_type_other", ""),
        "sample_identifier": get_field("sample_identifier", ""),
        "sample_description": get_field("sample_description", "Swab bucal (00000000000000)"),
        "clinical_indication": get_field(
            "clinical_indication",
            "História pessoal de câncer de mama aos 45 anos e história familiar para casos "
            "oncológicos (mãe com câncer de mama aos 49 anos).",
        ),

        # resultado principal
        "main_gene": get_field("main_gene"),
        "main_transcript": get_field("main_transcript"),
        "main_variant_c": get_field("main_variant_c"),
        "main_variant_p": get_field("main_variant_p"),
        "main_dbsnp": get_field("main_dbsnp"),
        "main_zygosity": get_field("main_zygosity"),
        "main_inheritance": get_field("main_inheritance"),
        "main_classification": get_field("main_classification"),
        "main_condition": get_field("main_condition"),
        "main_result_intro": get_field("main_result_intro"),

        # textos livres
        "interpretation_text": get_field("interpretation_text"),
        "interpretation_inheritance_mode": get_field("interpretation_inheritance_mode", "none"),
        "interpretation_obs": get_field("interpretation_obs", ""),
        "main_table_mode": get_field("main_table_mode", "variant"),
        "main_variant_extra_rows_text": get_field("main_variant_extra_rows_text", ""),
        "main_cnv_rows_text": get_field("main_cnv_rows_text", ""),
        "additional_findings_text": get_field("additional_findings_text"),
        "additional_findings_mode": get_field("additional_findings_mode", "manual"),
        "additional_findings_obs": get_field("additional_findings_obs", ""),
        "additional_table_mode": get_field("additional_table_mode", "variant"),
        "additional_variant_extra_rows_text": get_field("additional_variant_extra_rows_text", ""),
        "additional_cnv_rows_text": get_field("additional_cnv_rows_text", ""),
        "secondary_findings_mode": get_field("secondary_findings_mode", "manual"),
        "secondary_findings_text": get_field("secondary_findings_text", ""),
        "secondary_findings_obs": get_field("secondary_findings_obs", ""),
        "secondary_table_mode": get_field("secondary_table_mode", "variant"),
        "secondary_variant_rows_text": get_field("secondary_variant_rows_text", ""),
        "secondary_cnv_rows_text": get_field("secondary_cnv_rows_text", ""),

        # VUS / achados adicionais estruturados
        "vus_gene": get_field("vus_gene"),
        "vus_transcript": get_field("vus_transcript"),
        "vus_variant_c": get_field("vus_variant_c"),
        "vus_variant_p": get_field("vus_variant_p"),
        "vus_dbsnp": get_field("vus_dbsnp"),
        "vus_zygosity": get_field("vus_zygosity"),
        "vus_inheritance": get_field("vus_inheritance"),
        "vus_classification": get_field("vus_classification"),

        # métricas e recomendações
        "metrics_mode": get_field("metrics_mode", "panel"),
        "metrics_coverage_mean": get_field("metrics_coverage_mean"),
        "metrics_coverage_50x": get_field("metrics_coverage_50x"),
        "metrics_coverage_base": get_field("metrics_coverage_base", "50x"),
        "metrics_nuclear_base": get_field("metrics_nuclear_base", "30x"),
        "metrics_nuclear_percent": get_field("metrics_nuclear_percent", ""),
        "metrics_mito_base": get_field("metrics_mito_base", "100x"),
        "metrics_mito_percent": get_field("metrics_mito_percent", ""),
        "metrics_text": get_field("metrics_text"),
        "recommendations_text": get_field("recommendations_text"),
        "recommendations_mode": get_field("recommendations_mode", "manual"),
        "recommendations_obs": get_field("recommendations_obs", ""),
        "notes_text": get_field("notes_text"),
        "notes_obs": get_field("notes_obs", ""),

        # metodologia e limitações
        "methodology_mode": get_field("methodology_mode", "manual"),
        "methodology_text": get_field("methodology_text"),
        "limitations_text": get_field("limitations_text"),
        "observations_text": get_field("observations_text"),

        # genes analisados e referências
        "genes_analyzed_list": get_field("genes_analyzed_list"),
        "references_text": get_field("references_text"),

        # profissionais
        "analyst_name": get_field("analyst_name", ""),
        "analyst_registry": get_field("analyst_registry", ""),
        "lab_tech_name": get_field("lab_tech_name", ""),
        "lab_tech_registry": get_field("lab_tech_registry", ""),
        "geneticist_name": get_field("geneticist_name", ""),
        "geneticist_registry": get_field("geneticist_registry", ""),
        "director_name": get_field("director_name", ""),
        "director_registry": get_field("director_registry", ""),
        "tech_professional": get_field("tech_professional", "Erika Macedo"),
        "tech_professional_crbm": get_field("tech_professional_crbm", "CRBM-SP: 26338"),
        "md_responsible": get_field("md_responsible", "Dr. Guilherme Lugo"),
        "md_responsible_crm": get_field("md_responsible_crm", "CRM-SP: 256188"),
        "md_technical": get_field("md_technical", "Dra. Ângela F. L. Waitzberg"),
        "md_technical_crm": get_field("md_technical_crm", "CRM-SP: 69504"),
        "main_zygosity_options": MAIN_ZYGOSITY_OPTIONS,
        "main_inheritance_options": MAIN_INHERITANCE_OPTIONS,
        "main_classification_options": MAIN_CLASSIFICATION_OPTIONS,
        "interpretation_inheritance_mode_options": _build_mode_options(INTERPRETATION_INHERITANCE_MODE_OPTIONS),
        "additional_findings_mode_options": _build_mode_options(ADDITIONAL_FINDINGS_MODE_OPTIONS),
        "secondary_findings_mode_options": _build_mode_options(SECONDARY_FINDINGS_MODE_OPTIONS),
        "recommendations_mode_options": _build_mode_options(RECOMMENDATIONS_MODE_OPTIONS),
        "methodology_mode_options": _build_mode_options(METHODOLOGY_MODE_OPTIONS),
        "table_mode_options": _build_mode_options(TABLE_MODE_OPTIONS),
        "metrics_mode_options": _build_mode_options(METRICS_MODE_OPTIONS),
    }
    _normalize_main_dates(context)
    context["metrics_mode"] = (context.get("metrics_mode") or "panel").strip()
    if context["metrics_mode"] not in {"panel", "exome_mito"}:
        context["metrics_mode"] = "panel"
    context["metrics_coverage_base"] = _normalize_metrics_base(context.get("metrics_coverage_base"))
    context["metrics_nuclear_base"] = _normalize_metrics_base(context.get("metrics_nuclear_base"))
    context["metrics_mito_base"] = _normalize_metrics_base(context.get("metrics_mito_base"))
    context["patient_name"] = _normalize_patient_name(context.get("patient_name"))
    context["patient_birth_date_cover"] = context.get("patient_birth_date") or "00/00/0000"
    context["requester_name"] = _normalize_requester_name(context.get("requester_name"))

    table_payload = _build_rule_table_payload(context)
    context.update(table_payload)

    if context.get("main_variant_rows"):
        main_first = context["main_variant_rows"][0]
        context["main_gene"] = main_first.get("gene", context.get("main_gene", ""))
        context["main_transcript"] = main_first.get("transcript", context.get("main_transcript", ""))
        context["main_variant_c"] = main_first.get("variant_c", context.get("main_variant_c", ""))
        context["main_variant_p"] = main_first.get("variant_p", context.get("main_variant_p", ""))
        context["main_dbsnp"] = main_first.get("dbsnp", context.get("main_dbsnp", ""))
        context["main_zygosity"] = main_first.get("zygosity", context.get("main_zygosity", ""))
        context["main_inheritance"] = main_first.get("inheritance", context.get("main_inheritance", ""))
        context["main_classification"] = main_first.get("classification", context.get("main_classification", ""))
        if main_first.get("condition"):
            context["main_condition"] = main_first.get("condition")
    if context.get("additional_variant_rows"):
        add_first = context["additional_variant_rows"][0]
        context["vus_gene"] = add_first.get("gene", context.get("vus_gene", ""))
        context["vus_transcript"] = add_first.get("transcript", context.get("vus_transcript", ""))
        context["vus_variant_c"] = add_first.get("variant_c", context.get("vus_variant_c", ""))
        context["vus_variant_p"] = add_first.get("variant_p", context.get("vus_variant_p", ""))
        context["vus_dbsnp"] = add_first.get("dbsnp", context.get("vus_dbsnp", ""))
        context["vus_zygosity"] = add_first.get("zygosity", context.get("vus_zygosity", ""))
        context["vus_inheritance"] = add_first.get("inheritance", context.get("vus_inheritance", ""))
        context["vus_classification"] = add_first.get("classification", context.get("vus_classification", ""))

    context["is_admin"] = _is_admin(request.user)
    context["requester_not_identified"] = _to_bool(context.get("requester_not_identified"))
    context["requester_display"] = _format_requester_display(context)

    if not context.get("analyst_name"):
        context["analyst_name"] = defaults.get("analyst_name", "")
    if not context.get("analyst_registry"):
        context["analyst_registry"] = defaults.get("analyst_registry", "")
    if not context.get("lab_tech_name"):
        context["lab_tech_name"] = context.get("tech_professional") or defaults.get("lab_tech_name", "")
    if not context.get("lab_tech_registry"):
        context["lab_tech_registry"] = context.get("tech_professional_crbm") or defaults.get("lab_tech_registry", "")
    if not context.get("geneticist_name"):
        context["geneticist_name"] = context.get("md_responsible") or defaults.get("geneticist_name", "")
    if not context.get("geneticist_registry"):
        context["geneticist_registry"] = context.get("md_responsible_crm") or defaults.get("geneticist_registry", "")
    if not context.get("director_name"):
        context["director_name"] = context.get("md_technical") or defaults.get("director_name", "")
    if not context.get("director_registry"):
        context["director_registry"] = context.get("md_technical_crm") or defaults.get("director_registry", "")

    if not context.get("sample_type") and context.get("sample_description"):
        parsed_type, parsed_id = _parse_sample_description(context.get("sample_description"))
        mapping = {"swab bucal": "Swab bucal", "swab oral": "Swab bucal"}
        if parsed_type:
            key = parsed_type.lower()
            context["sample_type"] = mapping.get(key, parsed_type)
        if parsed_id:
            context["sample_identifier"] = context.get("sample_identifier") or parsed_id
    context["sample_display"] = _format_sample_display(context)

    zyg_choice, zyg_other = _resolve_select_value(context.get("main_zygosity", ""), MAIN_ZYGOSITY_OPTIONS)
    inh_choice, inh_other = _resolve_select_value(context.get("main_inheritance", ""), MAIN_INHERITANCE_OPTIONS)
    cls_choice, cls_other = _resolve_select_value(context.get("main_classification", ""), MAIN_CLASSIFICATION_OPTIONS)
    phenotype, omim = _split_condition_omim(context.get("main_condition", ""))

    context["main_zygosity_choice"] = zyg_choice
    context["main_zygosity_other"] = zyg_other
    context["main_inheritance_choice"] = inh_choice
    context["main_inheritance_other"] = inh_other
    context["main_classification_choice"] = cls_choice
    context["main_classification_other"] = cls_other
    context["main_condition_phenotype"] = phenotype
    context["main_condition_omim"] = _normalize_omim_number(omim) or MAIN_CONDITION_DEFAULT_OMIM
    context["main_inheritance_legend"] = _build_inheritance_legend(context.get("main_inheritance", ""))

    for field in [
        "interpretation_text",
        "additional_findings_text",
        "secondary_findings_text",
        "genes_analyzed_list",
        "notes_text",
        "recommendations_text",
        "methodology_text",
        "limitations_text",
        "observations_text",
        "references_text",
        "main_result_intro",
    ]:
        context[field] = _normalize_text_for_layout(context.get(field, ""))

    rendered_texts = _build_rule_based_texts(context)
    for field, value in rendered_texts.items():
        context[field] = _normalize_text_for_layout(value)

    layout_overflow = _parse_layout_overflow(request)

    # Template B: split texto por blocos para respeitar o layout fixo e reduzir overflows artificiais.
    if context.get("laudo_type") == "cancer_hereditario_144":
        interpretation_p2, interpretation_p3, interpretation_overflow = _split_interpretation_for_template_b(
            context.get("interpretation_text_rendered", ""),
            max_lines_p2=7,
            max_lines_p3=22,
            max_chars_per_line=96,
        )
        context["interpretation_p2"] = interpretation_p2
        context["interpretation_p3"] = interpretation_p3

        additional_p3, additional_overflow = _split_text_with_overflow(
            context.get("additional_findings_text_rendered", ""),
            first_lines=5,
            overflow_lines=34,
            max_chars_per_line=96,
        )
        context["additional_findings_p3"] = additional_p3

        genes_p4, genes_overflow = _split_text_with_overflow(
            context.get("genes_analyzed_list", ""),
            first_lines=11,
            overflow_lines=34,
        )
        context["genes_analyzed_p4"] = genes_p4
        methodology_p6, methodology_overflow = _split_text_with_overflow(
            context.get("methodology_text_rendered", ""),
            first_lines=10,
            overflow_lines=32,
            max_chars_per_line=96,
        )
        context["methodology_p6"] = methodology_p6

        limitations_p6, limitations_overflow = _split_text_with_overflow(
            context.get("limitations_text", ""),
            first_lines=12,
            overflow_lines=30,
            max_chars_per_line=96,
        )
        context["limitations_p6"] = limitations_p6

        observations_p6, observations_overflow_p6 = _split_text_with_overflow(
            context.get("observations_text", ""),
            first_lines=7,
            overflow_lines=28,
            max_chars_per_line=96,
        )
        context["observations_p6"] = observations_p6

        observations_p7_source = "\n\n".join(observations_overflow_p6).strip()
        observations_p7, observations_overflow = _split_text_with_overflow(
            observations_p7_source,
            first_lines=8,
            overflow_lines=28,
            max_chars_per_line=96,
        )
        context["observations_p7"] = observations_p7

        references_p7, references_overflow = _split_text_with_overflow(
            context.get("references_text", ""),
            first_lines=45,
            overflow_lines=34,
            max_chars_per_line=96,
        )
        context["references_p7"] = references_p7

        overflow_pages = []
        for title, chunks in [
            ("INTERPRETAÇÃO", interpretation_overflow),
            ("ACHADOS ADICIONAIS", additional_overflow),
            ("GENES ANALISADOS", genes_overflow),
            ("METODOLOGIA", methodology_overflow),
            ("CONSIDERAÇÕES E LIMITAÇÕES", limitations_overflow),
            ("OBSERVAÇÕES", observations_overflow),
            ("REFERÊNCIAS BIBLIOGRÁFICAS", references_overflow),
        ]:
            for chunk in chunks:
                overflow_pages.append({"title": title, "text": chunk})
        context["overflow_pages"] = overflow_pages
    else:
        context["interpretation_p2"] = context.get("interpretation_text_rendered", "")
        context["interpretation_p3"] = ""
        context["additional_findings_p3"] = context.get("additional_findings_text_rendered", "")
        context["genes_analyzed_p4"] = context.get("genes_analyzed_list", "")
        context["methodology_p6"] = context.get("methodology_text_rendered", "")
        context["limitations_p6"] = context.get("limitations_text", "")
        context["observations_p6"] = context.get("observations_text", "")
        context["observations_p7"] = ""
        context["references_p7"] = context.get("references_text", "")
        context["overflow_pages"] = []

    return context


def _get_report_from_request(request):
    report_id = request.POST.get("report_id")
    if not report_id:
        return None
    try:
        report_uuid = uuid.UUID(str(report_id))
    except ValueError:
        return None
    if _is_admin(request.user):
        return Report.objects.filter(id=report_uuid).first()
    return Report.objects.filter(id=report_uuid, workspace=request.workspace).first()


def _is_admin(user):
    return (
        user.is_authenticated
        and (
            user.is_superuser
            or user.is_staff
            or user.groups.filter(name="admin").exists()
        )
    )


def _update_report_from_request(report, request):
    previous_data = _normalize_report_data(report.data)
    data = _extract_report_data(request, previous_data)
    defaults = LAUDO_MODELOS.get(
        data.get("laudo_type"),
        LAUDO_MODELOS["cancer_hereditario_144"],
    )["defaults"]
    data["exam_name"] = _get_exam_name_for_type(data.get("laudo_type"))
    _normalize_main_dates(data)
    data["metrics_coverage_base"] = _normalize_metrics_base(data.get("metrics_coverage_base"))
    data["metrics_nuclear_base"] = _normalize_metrics_base(
        data.get("metrics_nuclear_base") or defaults.get("metrics_nuclear_base", "30x")
    )
    data["metrics_mito_base"] = _normalize_metrics_base(
        data.get("metrics_mito_base") or defaults.get("metrics_mito_base", "100x")
    )
    if not data.get("metrics_nuclear_percent"):
        data["metrics_nuclear_percent"] = defaults.get("metrics_nuclear_percent", "")
    if not data.get("metrics_mito_percent"):
        data["metrics_mito_percent"] = defaults.get("metrics_mito_percent", "")
    data["metrics_mode"] = (data.get("metrics_mode") or defaults.get("metrics_mode", "panel")).strip()
    if data["metrics_mode"] not in {"panel", "exome_mito"}:
        data["metrics_mode"] = "panel"
    data["patient_name"] = _normalize_patient_name(data.get("patient_name"))
    data["patient_birth_date_cover"] = data.get("patient_birth_date") or "00/00/0000"
    data["requester_name"] = _normalize_requester_name(data.get("requester_name"))
    data["main_table_mode"] = _normalize_table_mode(data.get("main_table_mode") or defaults.get("main_table_mode"))
    data["additional_table_mode"] = _normalize_table_mode(data.get("additional_table_mode") or defaults.get("additional_table_mode"))
    data["secondary_table_mode"] = _normalize_table_mode(data.get("secondary_table_mode") or defaults.get("secondary_table_mode"))
    data["main_variant_extra_rows_text"] = _rows_to_text(
        _parse_rows_text(data.get("main_variant_extra_rows_text"), VARIANT_LINE_FIELDS),
        VARIANT_LINE_FIELDS,
    )
    data["main_cnv_rows_text"] = _rows_to_text(
        _parse_rows_text(data.get("main_cnv_rows_text"), CNV_LINE_FIELDS),
        CNV_LINE_FIELDS,
    )
    data["additional_variant_extra_rows_text"] = _rows_to_text(
        _parse_rows_text(data.get("additional_variant_extra_rows_text"), VARIANT_LINE_FIELDS),
        VARIANT_LINE_FIELDS,
    )
    data["additional_cnv_rows_text"] = _rows_to_text(
        _parse_rows_text(data.get("additional_cnv_rows_text"), CNV_LINE_FIELDS),
        CNV_LINE_FIELDS,
    )
    data["secondary_variant_rows_text"] = _rows_to_text(
        _parse_rows_text(data.get("secondary_variant_rows_text"), VARIANT_LINE_FIELDS),
        VARIANT_LINE_FIELDS,
    )
    data["secondary_cnv_rows_text"] = _rows_to_text(
        _parse_rows_text(data.get("secondary_cnv_rows_text"), CNV_LINE_FIELDS),
        CNV_LINE_FIELDS,
    )
    if "vus_variant_c" not in request.POST:
        data["vus_variant_c"] = defaults.get("vus_variant_c", "")
    if _to_bool(data.get("requester_not_identified")):
        for key in [
            "requester_name",
            "requester_reg_type",
            "requester_reg_type_other",
            "requester_reg_number",
            "requester_reg_state",
        ]:
            data[key] = ""

    if data.get("sample_type") != "Outro":
        data["sample_type_other"] = ""

    # Resultado principal: aceita novos campos (select + "Outro") com fallback
    # para payload legado (inputs livres).
    resolved_zygosity = _resolve_select_post(
        request,
        "main_zygosity_choice",
        "main_zygosity_other",
        "main_zygosity",
        MAIN_ZYGOSITY_OPTIONS,
    )
    if resolved_zygosity:
        data["main_zygosity"] = resolved_zygosity

    resolved_inheritance = _resolve_select_post(
        request,
        "main_inheritance_choice",
        "main_inheritance_other",
        "main_inheritance",
        MAIN_INHERITANCE_OPTIONS,
    )
    if resolved_inheritance:
        data["main_inheritance"] = resolved_inheritance

    resolved_classification = _resolve_select_post(
        request,
        "main_classification_choice",
        "main_classification_other",
        "main_classification",
        MAIN_CLASSIFICATION_OPTIONS,
    )
    if resolved_classification:
        data["main_classification"] = resolved_classification

    if any(
        field in request.POST
        for field in ["main_condition_phenotype", "main_condition_omim", "main_condition"]
    ):
        current_phenotype, current_omim = _split_condition_omim(data.get("main_condition", ""))
        phenotype = (request.POST.get("main_condition_phenotype") or "").strip()
        if not phenotype and "main_condition" in request.POST:
            phenotype, _ = _split_condition_omim(request.POST.get("main_condition"))
        if not phenotype:
            phenotype = current_phenotype

        omim_post = request.POST.get("main_condition_omim")
        if omim_post is not None:
            omim = _normalize_omim_number(omim_post) or current_omim or MAIN_CONDITION_DEFAULT_OMIM
        else:
            omim = current_omim or MAIN_CONDITION_DEFAULT_OMIM
        data["main_condition"] = _compose_main_condition(phenotype, omim)

    table_payload = _build_rule_table_payload(data)
    if table_payload.get("main_variant_rows"):
        main_first = table_payload["main_variant_rows"][0]
        data["main_gene"] = main_first.get("gene", data.get("main_gene", ""))
        data["main_transcript"] = main_first.get("transcript", data.get("main_transcript", ""))
        data["main_variant_c"] = main_first.get("variant_c", data.get("main_variant_c", ""))
        data["main_variant_p"] = main_first.get("variant_p", data.get("main_variant_p", ""))
        data["main_dbsnp"] = main_first.get("dbsnp", data.get("main_dbsnp", ""))
        data["main_zygosity"] = main_first.get("zygosity", data.get("main_zygosity", ""))
        data["main_inheritance"] = main_first.get("inheritance", data.get("main_inheritance", ""))
        data["main_classification"] = main_first.get("classification", data.get("main_classification", ""))
        if main_first.get("condition"):
            data["main_condition"] = main_first.get("condition")
    if table_payload.get("additional_variant_rows"):
        add_first = table_payload["additional_variant_rows"][0]
        data["vus_gene"] = add_first.get("gene", data.get("vus_gene", ""))
        data["vus_transcript"] = add_first.get("transcript", data.get("vus_transcript", ""))
        data["vus_variant_c"] = add_first.get("variant_c", data.get("vus_variant_c", ""))
        data["vus_variant_p"] = add_first.get("variant_p", data.get("vus_variant_p", ""))
        data["vus_dbsnp"] = add_first.get("dbsnp", data.get("vus_dbsnp", ""))
        data["vus_zygosity"] = add_first.get("zygosity", data.get("vus_zygosity", ""))
        data["vus_inheritance"] = add_first.get("inheritance", data.get("vus_inheritance", ""))
        data["vus_classification"] = add_first.get("classification", data.get("vus_classification", ""))

    data["metrics_text"] = data.get("metrics_text", defaults.get("metrics_text", ""))
    if not data.get("metrics_coverage_base"):
        data["metrics_coverage_base"] = defaults.get("metrics_coverage_base", "50x")
    data["notes_text"] = data.get("notes_text", defaults.get("notes_text", ""))
    data["methodology_text"] = data.get("methodology_text", defaults.get("methodology_text", ""))
    data["limitations_text"] = data.get("limitations_text", defaults.get("limitations_text", ""))
    data["observations_text"] = data.get("observations_text", defaults.get("observations_text", ""))
    data["references_text"] = data.get("references_text", defaults.get("references_text", ""))
    if not _is_admin(request.user):
        data["recommendations_text"] = (report.data or {}).get(
            "recommendations_text",
            defaults.get("recommendations_text", ""),
        )
        data["genes_analyzed_list"] = (report.data or {}).get(
            "genes_analyzed_list",
            defaults.get("genes_analyzed_list", ""),
        )
    else:
        data["genes_analyzed_list"] = data.get(
            "genes_analyzed_list",
            defaults.get("genes_analyzed_list", ""),
        )
    if not data.get("analyst_name"):
        data["analyst_name"] = defaults.get("analyst_name", "")
    if not data.get("analyst_registry"):
        data["analyst_registry"] = defaults.get("analyst_registry", "")
    if not data.get("lab_tech_name"):
        data["lab_tech_name"] = data.get("tech_professional") or defaults.get("lab_tech_name", "")
    if not data.get("lab_tech_registry"):
        data["lab_tech_registry"] = data.get("tech_professional_crbm") or defaults.get("lab_tech_registry", "")
    if not data.get("geneticist_name"):
        data["geneticist_name"] = data.get("md_responsible") or defaults.get("geneticist_name", "")
    if not data.get("geneticist_registry"):
        data["geneticist_registry"] = data.get("md_responsible_crm") or defaults.get("geneticist_registry", "")
    if not data.get("director_name"):
        data["director_name"] = data.get("md_technical") or defaults.get("director_name", "")
    if not data.get("director_registry"):
        data["director_registry"] = data.get("md_technical_crm") or defaults.get("director_registry", "")

    if data.get("lab_tech_name"):
        data["tech_professional"] = data["lab_tech_name"]
    if data.get("lab_tech_registry"):
        data["tech_professional_crbm"] = data["lab_tech_registry"]
    if data.get("geneticist_name"):
        data["md_responsible"] = data["geneticist_name"]
    if data.get("geneticist_registry"):
        data["md_responsible_crm"] = data["geneticist_registry"]
    if data.get("director_name"):
        data["md_technical"] = data["director_name"]
    if data.get("director_registry"):
        data["md_technical_crm"] = data["director_registry"]

    _strip_legacy_obs_from_text(data, previous_data, request, "interpretation_text", "interpretation_obs")
    _strip_legacy_obs_from_text(data, previous_data, request, "additional_findings_text", "additional_findings_obs")
    _strip_legacy_obs_from_text(data, previous_data, request, "secondary_findings_text", "secondary_findings_obs")
    _strip_legacy_obs_from_text(data, previous_data, request, "recommendations_text", "recommendations_obs")
    _strip_legacy_obs_from_text(data, previous_data, request, "notes_text", "notes_obs")

    sample_display = _format_sample_display(data)
    if sample_display:
        data["sample_description"] = sample_display

    report.data = data
    report.report_type = data.get("laudo_type", report.report_type)
    if not report.title or report.title.strip() == DEFAULT_REPORT_TITLE:
        candidate = data.get("patient_name")
        if candidate and candidate != PLACEHOLDER_PATIENT_NAME:
            report.title = candidate
    report.save()
    return data


@login_required
def dashboard(request):
    query = request.GET.get("q", "").strip()
    is_admin = _is_admin(request.user)
    report_types = _get_report_type_options()
    type_labels = {opt["key"]: opt["label"] for opt in report_types}
    recent_reports = []
    try:
        if is_admin:
            reports = Report.objects.all().select_related("created_by").defer("data")
        else:
            reports = Report.objects.filter(workspace=request.workspace).defer("data")
        if query:
            reports = reports.filter(
                Q(title__icontains=query)
                | Q(data__patient_name__icontains=query)
                | Q(data__patient_code__icontains=query)
            )
        recent_reports = list(reports.order_by("-updated_at")[:10])
    except Exception:
        logger.exception("Dashboard reports failed for user_id=%s", request.user.id)
    for report in recent_reports:
        report.type_label = type_labels.get(report.report_type, report.report_type)
        if is_admin and report.created_by:
            display = report.created_by.get_full_name().strip()
            report.analyst_name = display or report.created_by.username
    try:
        if is_admin:
            folders = Folder.objects.all()
        else:
            folders = Folder.objects.filter(workspace=request.workspace)
        folders = folders.annotate(report_count=Count("reports"))
    except Exception:
        logger.exception("Dashboard folders failed for user_id=%s", request.user.id)
        folders = Folder.objects.none()
    context = {
        "recent_reports": recent_reports,
        "folders": folders,
        "query": query,
        "report_types": report_types,
        "is_admin": is_admin,
    }
    return render(request, "editor/dashboard.html", context)


@login_required
@require_http_methods(["POST"])
def create_folder(request):
    name = request.POST.get("name", "").strip()
    if name:
        Folder.objects.create(workspace=request.workspace, name=name)
    return redirect("dashboard")


@login_required
@require_http_methods(["GET", "POST"])
def report_new(request):
    if request.method == "POST":
        report_type = request.POST.get("report_type") or "cancer_hereditario_144"
        title = request.POST.get("title", "").strip() or DEFAULT_REPORT_TITLE
        folder_id = request.POST.get("folder_id")
        folder = None
        if folder_id:
            try:
                folder_uuid = uuid.UUID(str(folder_id))
            except ValueError:
                folder_uuid = None
            if folder_uuid:
                folder_qs = Folder.objects.filter(uuid=folder_uuid)
            else:
                folder_qs = Folder.objects.none()
            if not _is_admin(request.user):
                folder_qs = folder_qs.filter(workspace=request.workspace)
            folder = folder_qs.first()
        report = Report.objects.create(
            workspace=request.workspace,
            folder=folder,
            title=title,
            report_type=report_type,
            created_by=request.user,
            data={"laudo_type": report_type},
        )
        return redirect("report_editor", report_id=report.id)

    context = {
        "folders": Folder.objects.filter(workspace=request.workspace),
        "report_types": _get_report_type_options(),
    }
    return render(request, "editor/report_new.html", context)


@login_required
def folder_detail(request, folder_id):
    is_admin = _is_admin(request.user)
    if is_admin:
        folder = get_object_or_404(Folder, uuid=folder_id)
    else:
        folder = get_object_or_404(Folder, uuid=folder_id, workspace=request.workspace)
    query = request.GET.get("q", "").strip()
    if is_admin:
        reports = Report.objects.filter(folder=folder).select_related("created_by")
    else:
        reports = Report.objects.filter(workspace=request.workspace, folder=folder)
    if query:
        reports = reports.filter(
            Q(title__icontains=query)
            | Q(data__patient_name__icontains=query)
            | Q(data__patient_code__icontains=query)
        )
    reports = list(reports.order_by("-updated_at").defer("data"))
    type_labels = {opt["key"]: opt["label"] for opt in _get_report_type_options()}
    for report in reports:
        report.type_label = type_labels.get(report.report_type, report.report_type)
        if is_admin and report.created_by:
            display = report.created_by.get_full_name().strip()
            report.analyst_name = display or report.created_by.username
    context = {
        "folder": folder,
        "reports": reports,
        "query": query,
        "is_admin": is_admin,
    }
    return render(request, "editor/folder_detail.html", context)


@login_required
def report_editor(request, report_id):
    if _is_admin(request.user):
        report = get_object_or_404(Report, id=report_id)
    else:
        report = get_object_or_404(Report, id=report_id, workspace=request.workspace)
    base_data = _normalize_report_data(report.data, report.id)
    base_data.setdefault("laudo_type", report.report_type)
    context = _build_context(request, base_data=base_data)
    context["report"] = report
    context["report_types"] = _get_report_type_options()
    context["requester_reg_types"] = REQUESTER_REG_TYPES
    context["requester_uf_list"] = REQUESTER_UF_LIST
    context["sample_types"] = SAMPLE_TYPES
    context["professional_options"] = PROFESSIONAL_OPTIONS
    context["is_admin"] = _is_admin(request.user)
    context["preview_pdf_url"] = _get_preview_pdf_url(report.id)
    return render(request, "editor/editor_laudo.html", context)


@login_required
@require_http_methods(["POST"])
def report_delete(request, report_id):
    if _is_admin(request.user):
        report = get_object_or_404(Report, id=report_id)
    else:
        report = get_object_or_404(Report, id=report_id, workspace=request.workspace)
    redirect_target = "dashboard"
    if report.folder_id:
        redirect_target = "folder_detail"
        folder_id = report.folder.uuid
    report.delete()
    if redirect_target == "folder_detail":
        return redirect(redirect_target, folder_id=folder_id)
    return redirect(redirect_target)


@login_required
@require_http_methods(["POST"])
def report_duplicate(request, report_id):
    if _is_admin(request.user):
        report = get_object_or_404(Report, id=report_id)
    else:
        report = get_object_or_404(Report, id=report_id, workspace=request.workspace)
    copy_title = f"Copia de {report.title}" if report.title else DEFAULT_REPORT_TITLE
    new_report = Report.objects.create(
        workspace=report.workspace,
        folder=report.folder,
        title=copy_title,
        report_type=report.report_type,
        created_by=request.user,
        data=_normalize_report_data(report.data, report.id),
    )
    return redirect("report_editor", report_id=new_report.id)


@login_required
def user_manage(request):
    if not _is_admin(request.user):
        return HttpResponseForbidden("Acesso negado.")
    form_error = ""
    form_success = ""
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "").strip()
        full_name = request.POST.get("full_name", "").strip()
        email = request.POST.get("email", "").strip()
        role = request.POST.get("role", "analyst")

        if not username or not password:
            form_error = "Usuario e senha sao obrigatorios."
        elif User.objects.filter(username=username).exists():
            form_error = "Usuario ja existe."
        else:
            first_name = full_name
            last_name = ""
            if full_name and " " in full_name:
                parts = full_name.split()
                first_name = parts[0]
                last_name = " ".join(parts[1:])
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
            )
            if role == "admin":
                user.is_staff = True
                user.save(update_fields=["is_staff"])
            form_success = "Usuario criado com sucesso."

    users = User.objects.all().order_by("username")
    context = {
        "users": users,
        "form_error": form_error,
        "form_success": form_success,
    }
    return render(request, "editor/user_manage.html", context)


@login_required
@require_http_methods(["POST"])
def user_toggle_active(request, user_id):
    if not _is_admin(request.user):
        return HttpResponseForbidden("Acesso negado.")
    user = get_object_or_404(User, id=user_id)
    if user == request.user:
        return redirect("user_manage")
    user.is_active = not user.is_active
    user.save(update_fields=["is_active"])
    return redirect("user_manage")


def _render_pdf_bytes(request, context):
    # Geração manual (ReportLab), sem pipeline HTML/WeasyPrint.
    return render_template_b_pdf(context)


def _preview_pdf_path(report_id):
    return f"previews/{report_id}.pdf"


def _get_preview_pdf_url(report_id):
    path = _preview_pdf_path(report_id)
    if not default_storage.exists(path):
        return ""
    base = settings.MEDIA_URL or "/media/"
    base_path = urlparse(base).path or "/media/"
    if not base_path.startswith("/"):
        base_path = f"/{base_path}"
    if not base_path.endswith("/"):
        base_path += "/"
    return f"{base_path}previews/{report_id}.pdf"


@login_required
@require_http_methods(["POST"])
def export_pdf(request):
    # Usa o mesmo contexto da previa
    report = _get_report_from_request(request)
    if report:
        _update_report_from_request(report, request)
    context = _build_context(request, base_data=report.data if report else None)

    try:
        pdf_bytes = _render_pdf_bytes(request, context)
    except Exception:
        logging.exception("Erro ao gerar PDF (Template B? %s)", context.get("laudo_type"))
        raise

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = 'inline; filename="laudo.pdf"'
    return response


@login_required
@require_http_methods(["POST"])
def preview_pdf(request):
    report = _get_report_from_request(request)
    if report:
        _update_report_from_request(report, request)
    if not report:
        return JsonResponse({"error": "Relatorio nao encontrado."}, status=404)
    context = _build_context(request, base_data=report.data if report else None)
    try:
        pdf_bytes = _render_pdf_bytes(request, context)
    except Exception:
        logging.exception("Erro ao gerar PDF de previa (Template B? %s)", context.get("laudo_type"))
        return JsonResponse({"error": "Falha ao gerar previa."}, status=500)
    path = _preview_pdf_path(report.id)
    if default_storage.exists(path):
        default_storage.delete(path)
    default_storage.save(path, ContentFile(pdf_bytes))
    return JsonResponse({"url": _get_preview_pdf_url(report.id)})
