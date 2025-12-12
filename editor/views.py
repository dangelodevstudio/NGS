from django.shortcuts import render
from django.views.decorators.http import require_POST, require_http_methods
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.contrib.staticfiles import finders
import pdfkit
import os

# Modelos de laudo e respectivos valores padrÃ£o
LAUDO_MODELOS = {
    "cancer_hereditario_144": {
        "label": "PAINEL NGS PARA CÂNCER HEREDITÁRIO - 144 GENES",
        "defaults": {
            "exam_name": "PAINEL NGS PARA CÂNCER HEREDITÁRIO - 144 GENES",
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
                "Variante germinativa patogênica em TP53 associada à síndrome de Li-Fraumeni. "
                "O achado é consistente com predisposição hereditária a neoplasias. "
                "Recomenda-se avaliação genética em familiares de primeiro grau e seguimento especializado.\n\n"
                "Esta interpretação considera histórico pessoal/familiar informado e correlação clínico-genética."
            ),
            "vus_gene": "—",
            "vus_transcript": "—",
            "vus_variant_c": "—",
            "vus_variant_p": "—",
            "vus_dbsnp": "—",
            "vus_zygosity": "—",
            "vus_inheritance": "—",
            "vus_classification": "VUS",
            "additional_findings_text": (
                "Não foram identificadas variantes adicionais clinicamente acionáveis. "
                "Outras variantes classificadas como VUS devem ser reavaliadas conforme surgirem novos dados na literatura."
            ),
            "metrics_coverage_mean": "350x",
            "metrics_coverage_50x": "98%",
            "metrics_text": (
                "Cobertura média do painel: 350x; 98% das bases com cobertura ≥50x. "
                "Regiões com cobertura inferior foram avaliadas e não impactam a interpretação clínica principal."
            ),
            "recommendations_text": (
                "Recomenda-se aconselhamento genético e rastreamento específico conforme diretrizes vigentes "
                "para síndrome de Li-Fraumeni. Avaliar testagem em familiares de primeiro grau."
            ),
            "notes_text": (
                "O laudo deve ser correlacionado ao quadro clínico e histórico familiar informado. "
                "Atualizações futuras podem ser necessárias conforme novas evidências científicas."
            ),
            "methodology_text": (
                "Sequenciamento de nova geração (NGS) com captura híbrida de regiões codificantes e "
                "splice-sites dos genes do painel. Alinhamento ao genoma de referência GRCh37/hg19 e "
                "chamada de variantes por pipeline validado. Variantes confirmatórias por Sanger conforme necessidade."
            ),
            "limitations_text": (
                "O teste não detecta alterações estruturais complexas, expansões de repetições, "
                "mosaicismo em baixos níveis ou variantes em regiões intrônicas profundas. "
                "Cobertura incompleta pode ocorrer em regiões com alto conteúdo GC ou pseudogenes."
            ),
            "observations_text": (
                "Interpretação realizada segundo guias ACMG/AMP e evidências disponíveis na data de emissão. "
                "Resultados negativos não excluem completamente predisposição hereditária."
            ),
            "genes_analyzed_list": (
                "Lista dos 144 genes analisados conforme painel Bioma Genetics para câncer hereditário. "
                "Exemplos: TP53, BRCA1, BRCA2, PALB2, CHEK2, PTEN, CDH1, MLH1, MSH2, MSH6, PMS2, APC, "
                "STK11, ATM, NBN, RAD51C, RAD51D, entre outros."
            ),
            "references_text": (
                "Referências: ACMG/AMP guidelines; ClinVar; gnomAD; NCCN Guidelines para predisposição hereditária ao câncer; "
                "literatura científica atualizada até a data de emissão."
            ),
        },
    },
    # No futuro vamos adicionar mais modelos aqui (epilepsia, neuro, etc.)
}



def _build_context_from_request(request):
    # tipo de laudo selecionado (default = cÃ¢ncer hereditÃ¡rio 144 genes)
    laudo_type = request.POST.get('laudo_type', 'cancer_hereditario_144')
    modelo = LAUDO_MODELOS.get(laudo_type, LAUDO_MODELOS['cancer_hereditario_144'])
    defaults = modelo["defaults"]

    # helper para pegar valor do POST ou usar default
    def get_field(name, fallback=None):
        if fallback is None:
            fallback = defaults.get(name, '')
        return request.POST.get(name, fallback)

    context = {
        # manter tipo de laudo no contexto (para o select e para a prÃ©via)
        'laudo_type': laudo_type,

        # dados do paciente (sempre editÃ¡veis, com placeholders)
        'patient_name': get_field('patient_name', 'NOME COMPLETO PACIENTE'),
        'patient_birth_date': get_field('patient_birth_date', '00/00/0000'),
        'patient_sex': get_field('patient_sex', 'Feminino'),
        'patient_code': get_field('patient_code', '0000000000'),

        # dados do exame
        'exam_name': get_field('exam_name'),
        'exam_entry_date': get_field('exam_entry_date', '00/00/0000'),
        'exam_release_date': get_field('exam_release_date', '00/00/0000'),

        # solicitante / amostra
        'requester_name': get_field('requester_name', 'Dr(a). Fulana de Tal CRM - BR 8141'),
        'sample_description': get_field('sample_description', 'Swab bucal (00000000000000)'),
        'clinical_indication': get_field(
            'clinical_indication',
            'HistÃ³ria pessoal/familiar de cÃ¢ncer, etc.'
        ),

        # resultado principal
        'main_gene': get_field('main_gene'),
        'main_transcript': get_field('main_transcript'),
        'main_variant_c': get_field('main_variant_c'),
        'main_variant_p': get_field('main_variant_p'),
        'main_dbsnp': get_field('main_dbsnp'),
        'main_zygosity': get_field('main_zygosity'),
        'main_inheritance': get_field('main_inheritance'),
        'main_classification': get_field('main_classification'),
        'main_condition': get_field('main_condition'),
        'main_result_intro': get_field('main_result_intro'),

        # textos livres
        'interpretation_text': get_field('interpretation_text'),
        'additional_findings_text': get_field('additional_findings_text'),

        # VUS / achados adicionais estruturados
        'vus_gene': get_field('vus_gene'),
        'vus_transcript': get_field('vus_transcript'),
        'vus_variant_c': get_field('vus_variant_c'),
        'vus_variant_p': get_field('vus_variant_p'),
        'vus_dbsnp': get_field('vus_dbsnp'),
        'vus_zygosity': get_field('vus_zygosity'),
        'vus_inheritance': get_field('vus_inheritance'),
        'vus_classification': get_field('vus_classification'),

        # mÃ©tricas e recomendaÃ§Ãµes
        'metrics_coverage_mean': get_field('metrics_coverage_mean'),
        'metrics_coverage_50x': get_field('metrics_coverage_50x'),
        'metrics_text': get_field('metrics_text'),
        'recommendations_text': get_field('recommendations_text'),
        'notes_text': get_field('notes_text'),

        # metodologia e limitaÃ§Ãµes
        'methodology_text': get_field('methodology_text'),
        'limitations_text': get_field('limitations_text'),
        'observations_text': get_field('observations_text'),

        # genes analisados e referÃªncias
        'genes_analyzed_list': get_field('genes_analyzed_list'),
        'references_text': get_field('references_text'),

        # profissionais
        'tech_professional': get_field('tech_professional', 'Erika Macedo'),
        'tech_professional_crbm': get_field('tech_professional_crbm', 'CRBM-SP: 26338'),
        'md_responsible': get_field('md_responsible', 'Dr. Guilherme Lugo'),
        'md_responsible_crm': get_field('md_responsible_crm', 'CRM-SP: 256188'),
        'md_technical': get_field('md_technical', 'Dra. Ãngela F. L. Waitzberg'),
        'md_technical_crm': get_field('md_technical_crm', 'CRM-SP: 69504'),
    }

    return context


def editor_home(request):
    context = _build_context_from_request(request)
    return render(request, 'editor/editor_laudo.html', context)


@require_POST
def preview_laudo(request):
    context = _build_context_from_request(request)
    return render(request, 'editor/preview_sample.html', context)


def get_pdfkit_config():
    # Ajuste este caminho se o wkhtmltopdf estiver instalado em outro lugar
    wkhtmltopdf_path = r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"
    if os.path.isfile(wkhtmltopdf_path):
        return pdfkit.configuration(wkhtmltopdf=wkhtmltopdf_path)
    # Se nÃ£o encontrar o executÃ¡vel nesse caminho, tente usar o wkhtmltopdf do PATH
    return None


@require_http_methods(["POST"])
def export_pdf(request):
    # Usa o mesmo contexto da pr?via
    context = _build_context_from_request(request)

    # Renderiza o mesmo template da pr?via
    html_string = render_to_string("editor/preview_pdf.html", context, request=request)

    # Localiza os arquivos CSS (principal + overrides para PDF)
    main_css = finders.find("editor/css/style.css")
    pdf_override_css = finders.find("editor/css/pdf_overrides.css")
    css_files = [path for path in [main_css, pdf_override_css] if path]

    # Configura??o do wkhtmltopdf
    config = get_pdfkit_config()

    pdf_options = {
        "page-size": "A4",
        "encoding": "UTF-8",
        "margin-top": "10mm",
        "margin-right": "10mm",
        "margin-bottom": "10mm",
        "margin-left": "10mm",
        "enable-local-file-access": "",
    }

    if config is not None:
        pdf_bytes = pdfkit.from_string(
            html_string,
            False,
            options=pdf_options,
            configuration=config,
            css=css_files
        )
    else:
        # Tenta sem config expl?cita, assumindo wkhtmltopdf no PATH
        pdf_bytes = pdfkit.from_string(
            html_string,
            False,
            options=pdf_options,
            css=css_files
        )

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = 'inline; filename="laudo.pdf"'
    return response
