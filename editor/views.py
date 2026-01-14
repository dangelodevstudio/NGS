from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST, require_http_methods
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.contrib.staticfiles import finders
from django.db.models import Q
from pathlib import Path
import uuid
import pdfkit
import os
import logging
from .models import Folder, Report

# Wkhtmltopdf (versão dos repositórios do Ubuntu) depende dos plugins Qt.
# No Heroku eles ficam em /app/.apt/usr/lib/...; configuramos o caminho aqui
# para evitar o erro "Could not find the Qt platform plugin offscreen".
QT_PLATFORM_PATH = "/app/.apt/usr/lib/x86_64-linux-gnu/qt5/plugins/platforms"
if os.path.isdir(QT_PLATFORM_PATH):
    os.environ.setdefault("QT_QPA_PLATFORM_PLUGIN_PATH", QT_PLATFORM_PATH)
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

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
    "additional_findings_text",
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
    "metrics_text",
    "recommendations_text",
    "notes_text",
    "methodology_text",
    "limitations_text",
    "observations_text",
    "genes_analyzed_list",
    "references_text",
    "tech_professional",
    "tech_professional_crbm",
    "md_responsible",
    "md_responsible_crm",
    "md_technical",
    "md_technical_crm",
]

DEFAULT_REPORT_TITLE = "Novo laudo"
PLACEHOLDER_PATIENT_NAME = "NOME COMPLETO PACIENTE"


def _get_report_type_options():
    return [{"key": key, "label": value["label"]} for key, value in LAUDO_MODELOS.items()]


def _resolve_laudo_type(request, base_data=None):
    return (
        request.POST.get("laudo_type")
        or (base_data or {}).get("laudo_type")
        or "cancer_hereditario_144"
    )

def _split_interpretation_for_template_b(text, first_limit=900):
    """
    Divide o texto de interpreta??o em duas partes aproximadas para o template B.
    Usa quebras de par?grafo ou senten?as para evitar cortes abruptos.
    """
    if not text:
        return "", ""
    cleaned = text.strip()
    if len(cleaned) <= first_limit:
        return cleaned, ""
    slice_text = cleaned[:first_limit]
    split_at = max(slice_text.rfind("\n\n"), slice_text.rfind(". "))
    if split_at == -1 or split_at < first_limit * 0.5:
        split_at = first_limit
    part1 = cleaned[:split_at].strip()
    part2 = cleaned[split_at:].strip()
    return part1, part2




def _extract_report_data(request, base_data=None):
    data = {}
    source = base_data or {}
    for field in REPORT_FIELDS:
        if request.method == "POST" and field in request.POST:
            data[field] = request.POST.get(field, "")
        elif field in source:
            data[field] = source.get(field)
    if "laudo_type" not in data:
        data["laudo_type"] = _resolve_laudo_type(request, base_data)
    return data


def _build_context(request, base_data=None):
    # tipo de laudo selecionado (default = c??ncer heredit??rio 144 genes)
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
        # manter tipo de laudo no contexto (para o select e para a pr??via)
        "laudo_type": laudo_type,

        # dados do paciente (sempre edit??veis, com placeholders)
        "patient_name": get_field("patient_name", "NOME COMPLETO PACIENTE"),
        "patient_birth_date": get_field("patient_birth_date", "00/00/0000"),
        "patient_sex": get_field("patient_sex", "Feminino"),
        "patient_code": get_field("patient_code", "0000000000"),

        # dados do exame
        "exam_name": get_field("exam_name"),
        "exam_entry_date": get_field("exam_entry_date", "00/00/0000"),
        "exam_release_date": get_field("exam_release_date", "00/00/0000"),

        # solicitante / amostra
        "requester_name": get_field("requester_name", "Dr(a). Fulana de Tal CRM - BR 8141"),
        "sample_description": get_field("sample_description", "Swab bucal (00000000000000)"),
        "clinical_indication": get_field(
            "clinical_indication",
            "Hist??ria pessoal/familiar de c??ncer, etc.",
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
        "additional_findings_text": get_field("additional_findings_text"),

        # VUS / achados adicionais estruturados
        "vus_gene": get_field("vus_gene"),
        "vus_transcript": get_field("vus_transcript"),
        "vus_variant_c": get_field("vus_variant_c"),
        "vus_variant_p": get_field("vus_variant_p"),
        "vus_dbsnp": get_field("vus_dbsnp"),
        "vus_zygosity": get_field("vus_zygosity"),
        "vus_inheritance": get_field("vus_inheritance"),
        "vus_classification": get_field("vus_classification"),

        # m??tricas e recomenda????es
        "metrics_coverage_mean": get_field("metrics_coverage_mean"),
        "metrics_coverage_50x": get_field("metrics_coverage_50x"),
        "metrics_text": get_field("metrics_text"),
        "recommendations_text": get_field("recommendations_text"),
        "notes_text": get_field("notes_text"),

        # metodologia e limita????es
        "methodology_text": get_field("methodology_text"),
        "limitations_text": get_field("limitations_text"),
        "observations_text": get_field("observations_text"),

        # genes analisados e refer??ncias
        "genes_analyzed_list": get_field("genes_analyzed_list"),
        "references_text": get_field("references_text"),

        # profissionais
        "tech_professional": get_field("tech_professional", "Erika Macedo"),
        "tech_professional_crbm": get_field("tech_professional_crbm", "CRBM-SP: 26338"),
        "md_responsible": get_field("md_responsible", "Dr. Guilherme Lugo"),
        "md_responsible_crm": get_field("md_responsible_crm", "CRM-SP: 256188"),
        "md_technical": get_field("md_technical", "Dra. ??ngela F. L. Waitzberg"),
        "md_technical_crm": get_field("md_technical_crm", "CRM-SP: 69504"),
    }

    # Ajustes espec??ficos para template B (split de interpreta????o)
    if context.get("laudo_type") == "cancer_hereditario_144":
        part1, part2 = _split_interpretation_for_template_b(context.get("interpretation_text", ""))
        context["interpretation_p2"] = part1
        context["interpretation_p3"] = part2
    else:
        context["interpretation_p2"] = context.get("interpretation_text", "")
        context["interpretation_p3"] = ""

    return context


def _get_report_from_request(request):
    report_id = request.POST.get("report_id")
    if not report_id:
        return None
    try:
        report_uuid = uuid.UUID(str(report_id))
    except ValueError:
        return None
    return Report.objects.filter(id=report_uuid, workspace=request.workspace).first()


def _update_report_from_request(report, request):
    data = _extract_report_data(request, report.data or {})
    report.data = data
    report.report_type = data.get("laudo_type", report.report_type)
    if not report.title or report.title.strip() == DEFAULT_REPORT_TITLE:
        candidate = data.get("patient_name")
        if candidate and candidate != PLACEHOLDER_PATIENT_NAME:
            report.title = candidate
    report.save()
    return data


def dashboard(request):
    query = request.GET.get("q", "").strip()
    reports = Report.objects.filter(workspace=request.workspace)
    if query:
        reports = reports.filter(
            Q(title__icontains=query)
            | Q(data__patient_name__icontains=query)
            | Q(data__patient_code__icontains=query)
        )
    recent_reports = list(reports.order_by("-updated_at")[:10])
    report_types = _get_report_type_options()
    type_labels = {opt["key"]: opt["label"] for opt in report_types}
    for report in recent_reports:
        report.type_label = type_labels.get(report.report_type, report.report_type)
    folders = Folder.objects.filter(workspace=request.workspace).prefetch_related("reports")
    context = {
        "recent_reports": recent_reports,
        "folders": folders,
        "query": query,
        "report_types": report_types,
    }
    return render(request, "editor/dashboard.html", context)


@require_http_methods(["POST"])
def create_folder(request):
    name = request.POST.get("name", "").strip()
    if name:
        Folder.objects.create(workspace=request.workspace, name=name)
    return redirect("dashboard")


@require_http_methods(["GET", "POST"])
def report_new(request):
    if request.method == "POST":
        report_type = request.POST.get("report_type") or "cancer_hereditario_144"
        title = request.POST.get("title", "").strip() or DEFAULT_REPORT_TITLE
        folder_id = request.POST.get("folder_id")
        folder = None
        if folder_id:
            folder = Folder.objects.filter(id=folder_id, workspace=request.workspace).first()
        report = Report.objects.create(
            workspace=request.workspace,
            folder=folder,
            title=title,
            report_type=report_type,
            data={"laudo_type": report_type},
        )
        return redirect("report_editor", report_id=report.id)

    context = {
        "folders": Folder.objects.filter(workspace=request.workspace),
        "report_types": _get_report_type_options(),
    }
    return render(request, "editor/report_new.html", context)


def folder_detail(request, folder_id):
    folder = get_object_or_404(Folder, id=folder_id, workspace=request.workspace)
    query = request.GET.get("q", "").strip()
    reports = list(
        Report.objects.filter(workspace=request.workspace, folder=folder).order_by("-updated_at")
    )
    type_labels = {opt["key"]: opt["label"] for opt in _get_report_type_options()}
    for report in reports:
        report.type_label = type_labels.get(report.report_type, report.report_type)
    if query:
        reports = [
            report
            for report in reports
            if query.lower() in (report.title or "").lower()
            or query.lower() in (report.data or {}).get("patient_name", "").lower()
            or query.lower() in (report.data or {}).get("patient_code", "").lower()
        ]
    context = {
        "folder": folder,
        "reports": reports,
        "query": query,
    }
    return render(request, "editor/folder_detail.html", context)


def report_editor(request, report_id):
    report = get_object_or_404(Report, id=report_id, workspace=request.workspace)
    base_data = dict(report.data or {})
    base_data.setdefault("laudo_type", report.report_type)
    context = _build_context(request, base_data=base_data)
    context["report"] = report
    context["report_types"] = _get_report_type_options()
    return render(request, "editor/editor_laudo.html", context)


@require_http_methods(["POST"])
def report_delete(request, report_id):
    report = get_object_or_404(Report, id=report_id, workspace=request.workspace)
    redirect_target = "dashboard"
    if report.folder_id:
        redirect_target = "folder_detail"
        folder_id = report.folder_id
    report.delete()
    if redirect_target == "folder_detail":
        return redirect(redirect_target, folder_id=folder_id)
    return redirect(redirect_target)


@require_http_methods(["POST"])
def report_duplicate(request, report_id):
    report = get_object_or_404(Report, id=report_id, workspace=request.workspace)
    copy_title = f"Copia de {report.title}" if report.title else DEFAULT_REPORT_TITLE
    new_report = Report.objects.create(
        workspace=request.workspace,
        folder=report.folder,
        title=copy_title,
        report_type=report.report_type,
        data=dict(report.data or {}),
    )
    return redirect("report_editor", report_id=new_report.id)


@require_POST
def preview_laudo(request):
    report = _get_report_from_request(request)
    if report:
        _update_report_from_request(report, request)
    context = _build_context(request, base_data=report.data if report else None)
    template_name = "editor/preview_sample.html"
    if context.get("laudo_type") == "cancer_hereditario_144":
        template_name = "editor/preview_sample_b.html"
    return render(request, template_name, context)


def get_pdfkit_config():
    # Ajuste este caminho se o wkhtmltopdf estiver instalado em outro lugar
    candidate_paths = [
        os.environ.get("WKHTMTOPDF_PATH"),
        os.environ.get("WKHTMLTOPDF_PATH"),
        r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe",
        "/usr/bin/wkhtmltopdf",
    ]
    for path in candidate_paths:
        if path and os.path.isfile(path):
            return pdfkit.configuration(wkhtmltopdf=path)
    # Se nÃ£o encontrar o executÃ¡vel nesse caminho, tente usar o wkhtmltopdf do PATH
    return None


@require_http_methods(["POST"])
def export_pdf(request):
    # Usa o mesmo contexto da pr?via
    report = _get_report_from_request(request)
    if report:
        _update_report_from_request(report, request)
    context = _build_context(request, base_data=report.data if report else None)

    # Seleciona o template e CSS conforme o tipo de laudo
    template_name = "editor/preview_pdf.html"
    css_files = []
    pdf_options = {
        "page-size": "A4",
        "encoding": "UTF-8",
        "margin-top": "10mm",
        "margin-right": "10mm",
        "margin-bottom": "10mm",
        "margin-left": "10mm",
        "enable-local-file-access": "",
    }

    if context.get("laudo_type") == "cancer_hereditario_144":
        template_name = "editor/preview_sample_b.html"
        css_b = finders.find("editor/css/pdf_template_b.css")
        if css_b:
            css_files = [css_b]
        # Monta caminhos absolutos para os fundos das 8 p?ginas
        bg_pages = []
        for i in range(1, 9):
            path_bg = finders.find(f"editor/img/templates/laudo144_pg0{i}.png")
            if path_bg:
                bg_pages.append(Path(path_bg).resolve().as_uri())
            else:
                bg_pages.append(f"/static/editor/img/templates/laudo144_pg0{i}.png")
        context = dict(context, bg_pages=bg_pages)
        pdf_options = {
            "page-size": "A4",
            "encoding": "UTF-8",
            "margin-top": "0mm",
            "margin-right": "0mm",
            "margin-bottom": "0mm",
            "margin-left": "0mm",
            "enable-local-file-access": True,
            "disable-smart-shrinking": "",
            "print-media-type": "",
            "load-error-handling": "ignore",
            "load-media-error-handling": "ignore",
        }
    else:
        main_css = finders.find("editor/css/style.css")
        pdf_override_css = finders.find("editor/css/pdf_overrides.css")
        css_files = [p for p in [main_css, pdf_override_css] if p]

    # Renderiza o template escolhido
    html_string = render_to_string(template_name, context, request=request)

    # Configura??o do wkhtmltopdf
    config = get_pdfkit_config()

    try:
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
    except Exception:
        logging.exception("Erro ao gerar PDF (Template B? %s)", context.get("laudo_type"))
        raise

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = 'inline; filename="laudo.pdf"'
    return response
