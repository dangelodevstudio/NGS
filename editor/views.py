from django.shortcuts import render
from django.views.decorators.http import require_POST

def _build_context_from_request(request):
    return {
        'patient_name': request.POST.get('patient_name', 'Paciente Exemplo'),
        'patient_code': request.POST.get('patient_code', 'BIO-0001'),
        'birth_date': request.POST.get('birth_date', '01/01/1990'),
        'exam_type': request.POST.get('exam_type', 'Painel Farmacogenômico - Demo'),
        'responsible_doctor': request.POST.get('responsible_doctor', 'Dr(a). Nome Exemplo'),
        'gene_profile': request.POST.get('gene_profile', 'Metabolizador intermediário'),
        'risk_level': request.POST.get('risk_level', 'moderado'),
        'highlight_gene': request.POST.get('highlight_gene', 'CYP2D6'),
        'notes': request.POST.get('notes', 'Observação clínica resumida sobre o paciente e seus achados genéticos.'),
    }

def editor_home(request):
    context = _build_context_from_request(request)
    return render(request, 'editor/editor_laudo.html', context)

@require_POST
def preview_laudo(request):
    context = _build_context_from_request(request)
    return render(request, 'editor/preview_sample.html', context)
