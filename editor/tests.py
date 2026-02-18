from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from .models import Report, Workspace
from .views import (
    LAUDO_MODELOS,
    _build_context,
    _build_inheritance_legend,
    _normalize_date_ddmmyyyy,
    _get_exam_name_for_type,
    _split_condition_omim,
    _update_report_from_request,
)


class MainResultControlsTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username="tester", password="secret")
        self.workspace = Workspace.objects.create(user=self.user)
        self.defaults = LAUDO_MODELOS["cancer_hereditario_144"]["defaults"]

    def test_split_condition_omim_parses_expected_format(self):
        phenotype, omim = _split_condition_omim("Síndrome de Li-Fraumeni (OMIM:#151623)")
        self.assertEqual(phenotype, "Síndrome de Li-Fraumeni")
        self.assertEqual(omim, "151623")

    def test_split_condition_omim_falls_back_to_default_when_missing(self):
        phenotype, omim = _split_condition_omim("Síndrome de Li-Fraumeni")
        self.assertEqual(phenotype, "Síndrome de Li-Fraumeni")
        self.assertEqual(omim, "151623")

    def test_build_context_maps_legacy_values_to_outro(self):
        request = self.factory.get("/")
        request.user = self.user
        context = _build_context(
            request,
            base_data={
                "laudo_type": "cancer_hereditario_144",
                "main_zygosity": "Zigosidade custom",
                "main_inheritance": "Herança custom",
                "main_classification": "Classe custom",
                "main_condition": "Fenótipo legado (OMIM:#000001)",
            },
        )

        self.assertEqual(context["main_zygosity_choice"], "Outro")
        self.assertEqual(context["main_zygosity_other"], "Zigosidade custom")
        self.assertEqual(context["main_inheritance_choice"], "Outro")
        self.assertEqual(context["main_inheritance_other"], "Herança custom")
        self.assertEqual(context["main_classification_choice"], "Outro")
        self.assertEqual(context["main_classification_other"], "Classe custom")
        self.assertEqual(context["main_condition_phenotype"], "Fenótipo legado")
        self.assertEqual(context["main_condition_omim"], "000001")

    def test_update_report_from_request_persists_new_selector_fields(self):
        report = Report.objects.create(
            workspace=self.workspace,
            created_by=self.user,
            title="Laudo",
            report_type="cancer_hereditario_144",
            data={"laudo_type": "cancer_hereditario_144", **self.defaults},
        )

        request = self.factory.post(
            "/preview/",
            data={
                "main_zygosity_choice": "Homozigose",
                "main_inheritance_choice": "Autossômica recessiva",
                "main_classification_choice": "Provavelmente patogênica",
                "main_condition_phenotype": "Fenótipo atualizado",
            },
        )
        request.user = self.user
        request.workspace = self.workspace

        data = _update_report_from_request(report, request)

        self.assertEqual(data["main_zygosity"], "Homozigose")
        self.assertEqual(data["main_inheritance"], "Autossômica recessiva")
        self.assertEqual(data["main_classification"], "Provavelmente patogênica")
        self.assertEqual(data["main_condition"], "Fenótipo atualizado (OMIM:#151623)")

    def test_update_report_from_request_allows_editing_only_omim_number(self):
        report = Report.objects.create(
            workspace=self.workspace,
            created_by=self.user,
            title="Laudo OMIM",
            report_type="cancer_hereditario_144",
            data={"laudo_type": "cancer_hereditario_144", **self.defaults},
        )

        request = self.factory.post(
            "/preview/",
            data={
                "main_condition_phenotype": "Fenótipo atualizado",
                "main_condition_omim": "OMIM:#000777",
            },
        )
        request.user = self.user
        request.workspace = self.workspace

        data = _update_report_from_request(report, request)
        self.assertEqual(data["main_condition"], "Fenótipo atualizado (OMIM:#000777)")

    def test_update_report_from_request_persists_custom_outro_values(self):
        report = Report.objects.create(
            workspace=self.workspace,
            created_by=self.user,
            title="Laudo 2",
            report_type="cancer_hereditario_144",
            data={"laudo_type": "cancer_hereditario_144", **self.defaults},
        )

        request = self.factory.post(
            "/preview/",
            data={
                "main_zygosity_choice": "Outro",
                "main_zygosity_other": "Mosaico",
                "main_inheritance_choice": "Outro",
                "main_inheritance_other": "Complexa",
                "main_classification_choice": "Outro",
                "main_classification_other": "Classificação custom",
                "main_condition_phenotype": "Fenótipo custom",
            },
        )
        request.user = self.user
        request.workspace = self.workspace

        data = _update_report_from_request(report, request)

        self.assertEqual(data["main_zygosity"], "Mosaico")
        self.assertEqual(data["main_inheritance"], "Complexa")
        self.assertEqual(data["main_classification"], "Classificação custom")
        self.assertEqual(data["main_condition"], "Fenótipo custom (OMIM:#151623)")

    def test_build_inheritance_legend_uses_mapping_and_custom_fallback(self):
        self.assertEqual(
            _build_inheritance_legend("Autossômica dominante"),
            "Modelo de herança: autossômica dominante (AD).",
        )
        self.assertEqual(
            _build_inheritance_legend("Herança rara custom"),
            "Modelo de herança: Herança rara custom.",
        )

    def test_exam_name_synced_from_laudo_type_in_context(self):
        request = self.factory.get("/")
        request.user = self.user
        context = _build_context(
            request,
            base_data={
                "laudo_type": "cancer_hereditario_144",
                "exam_name": "Nome digitado manualmente",
            },
        )
        self.assertEqual(context["exam_name"], _get_exam_name_for_type("cancer_hereditario_144"))

    def test_exam_name_synced_from_laudo_type_on_update(self):
        report = Report.objects.create(
            workspace=self.workspace,
            created_by=self.user,
            title="Laudo nome exame",
            report_type="cancer_hereditario_144",
            data={"laudo_type": "cancer_hereditario_144", **self.defaults},
        )
        request = self.factory.post("/preview/", data={"exam_name": "Nome inválido manual"})
        request.user = self.user
        request.workspace = self.workspace
        data = _update_report_from_request(report, request)
        self.assertEqual(data["exam_name"], _get_exam_name_for_type("cancer_hereditario_144"))

    def test_date_normalization_accepts_dash_and_dot(self):
        self.assertEqual(_normalize_date_ddmmyyyy("10-11-1994"), "10/11/1994")
        self.assertEqual(_normalize_date_ddmmyyyy("10.11.1994"), "10/11/1994")

    def test_date_normalization_invalid_goes_to_placeholder(self):
        self.assertEqual(_normalize_date_ddmmyyyy("abc"), "00/00/0000")
        self.assertEqual(_normalize_date_ddmmyyyy("3/2024"), "00/00/0000")

    def test_date_normalization_rejects_iso_and_compact(self):
        self.assertEqual(_normalize_date_ddmmyyyy("1994-11-10"), "00/00/0000")
        self.assertEqual(_normalize_date_ddmmyyyy("10111994"), "00/00/0000")

    def test_existing_valid_ddmmyyyy_is_preserved(self):
        self.assertEqual(_normalize_date_ddmmyyyy("10/11/1994"), "10/11/1994")

    def test_update_report_normalizes_dates_from_post(self):
        report = Report.objects.create(
            workspace=self.workspace,
            created_by=self.user,
            title="Laudo datas",
            report_type="cancer_hereditario_144",
            data={"laudo_type": "cancer_hereditario_144", **self.defaults},
        )
        request = self.factory.post(
            "/preview/",
            data={
                "patient_birth_date": "10-11-1994",
                "exam_entry_date": "10.12.2025",
                "exam_release_date": "invalida",
            },
        )
        request.user = self.user
        request.workspace = self.workspace

        data = _update_report_from_request(report, request)
        self.assertEqual(data["patient_birth_date"], "10/11/1994")
        self.assertEqual(data["exam_entry_date"], "10/12/2025")
        self.assertEqual(data["exam_release_date"], "00/00/0000")
