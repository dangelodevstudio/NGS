from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from .models import Report, Workspace
from .views import (
    LAUDO_MODELOS,
    _build_context,
    _build_inheritance_legend,
    _format_requester_display,
    _normalize_date_ddmmyyyy,
    _normalize_metrics_base,
    _resolve_inheritance_paragraph,
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

    def test_resolve_inheritance_paragraph_supports_synonyms_and_codes(self):
        from_synonym = _resolve_inheritance_paragraph("Ligado ao X")
        self.assertIn("ligado ao cromossomo X", from_synonym)

        from_code = _resolve_inheritance_paragraph("AR")
        self.assertIn("autossômico recessivo", from_code)

    def test_resolve_inheritance_paragraph_supports_dominant_recessive_combo(self):
        combo = _resolve_inheritance_paragraph("Autossômica dominante/recessiva")
        self.assertIn("autossômico dominante", combo)
        self.assertIn("autossômico recessivo", combo)

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

    def test_date_normalization_accepts_compact_ddmmyyyy_and_rejects_iso(self):
        self.assertEqual(_normalize_date_ddmmyyyy("1994-11-10"), "00/00/0000")
        self.assertEqual(_normalize_date_ddmmyyyy("10111994"), "10/11/1994")

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
                "patient_birth_date": "10111994",
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

    def test_build_context_syncs_cover_birth_date_and_uppercases_name(self):
        request = self.factory.get("/")
        request.user = self.user
        context = _build_context(
            request,
            base_data={
                "laudo_type": "cancer_hereditario_144",
                "patient_name": "wellington da silva",
                "patient_birth_date": "10.11.1994",
                "patient_birth_date_cover": "00/00/000",
            },
        )
        self.assertEqual(context["patient_name"], "WELLINGTON DA SILVA")
        self.assertEqual(context["patient_birth_date"], "10/11/1994")
        self.assertEqual(context["patient_birth_date_cover"], "10/11/1994")

    def test_update_report_uppercases_name_and_syncs_cover_birth_date(self):
        report = Report.objects.create(
            workspace=self.workspace,
            created_by=self.user,
            title="Laudo capa",
            report_type="cancer_hereditario_144",
            data={"laudo_type": "cancer_hereditario_144", **self.defaults},
        )
        request = self.factory.post(
            "/preview/",
            data={
                "patient_name": "wellington da silva",
                "patient_birth_date": "12121212",
            },
        )
        request.user = self.user
        request.workspace = self.workspace

        data = _update_report_from_request(report, request)
        self.assertEqual(data["patient_name"], "WELLINGTON DA SILVA")
        self.assertEqual(data["patient_birth_date"], "12/12/1212")
        self.assertEqual(data["patient_birth_date_cover"], "12/12/1212")

    def test_requester_display_does_not_duplicate_fixed_title(self):
        display = _format_requester_display(
            {
                "requester_name": "Dr(a). Juliana das Gracas",
                "requester_reg_type": "CRM",
                "requester_reg_number": "8141",
                "requester_reg_state": "BR",
            }
        )
        self.assertEqual(display, "Dr(a). Juliana das Gracas CRM - BR 8141")

    def test_build_context_normalizes_requester_name_for_input(self):
        request = self.factory.get("/")
        request.user = self.user
        context = _build_context(
            request,
            base_data={
                "laudo_type": "cancer_hereditario_144",
                "requester_name": "Dra. Juliana das Gracas",
            },
        )
        self.assertEqual(context["requester_name"], "Juliana das Gracas")
        self.assertEqual(context["requester_display"], "Dr(a). Juliana das Gracas")

    def test_metrics_base_normalization(self):
        self.assertEqual(_normalize_metrics_base("50"), "50x")
        self.assertEqual(_normalize_metrics_base("  30X "), "30x")
        self.assertEqual(_normalize_metrics_base(""), "50x")

    def test_update_report_persists_metrics_base(self):
        report = Report.objects.create(
            workspace=self.workspace,
            created_by=self.user,
            title="Laudo métricas",
            report_type="cancer_hereditario_144",
            data={"laudo_type": "cancer_hereditario_144", **self.defaults},
        )
        request = self.factory.post(
            "/preview/",
            data={
                "metrics_coverage_mean": "350x",
                "metrics_coverage_50x": "98%",
                "metrics_coverage_base": "60",
            },
        )
        request.user = self.user
        request.workspace = self.workspace

        data = _update_report_from_request(report, request)
        self.assertEqual(data["metrics_coverage_mean"], "350x")
        self.assertEqual(data["metrics_coverage_50x"], "98%")
        self.assertEqual(data["metrics_coverage_base"], "60x")

    def test_build_context_keeps_admin_editable_notes_and_methodology(self):
        request = self.factory.get("/")
        request.user = self.user
        context = _build_context(
            request,
            base_data={
                "laudo_type": "cancer_hereditario_144",
                "notes_text": "Texto custom de notas.",
                "methodology_text": "Texto custom de metodologia.",
            },
        )
        self.assertEqual(context["notes_text"], "Texto custom de notas.")
        self.assertEqual(context["methodology_text"], "Texto custom de metodologia.")

    def test_update_report_preserves_raw_interpretation_and_renders_tokens_in_context(self):
        report = Report.objects.create(
            workspace=self.workspace,
            created_by=self.user,
            title="Laudo token",
            report_type="cancer_hereditario_144",
            data={"laudo_type": "cancer_hereditario_144", **self.defaults},
        )
        request = self.factory.post(
            "/preview/",
            data={
                "interpretation_inheritance_mode": "none",
                "interpretation_text": "Texto base @AR",
            },
        )
        request.user = self.user
        request.workspace = self.workspace

        data = _update_report_from_request(report, request)
        self.assertEqual(data["interpretation_text"], "Texto base @AR")

        context_request = self.factory.get("/")
        context_request.user = self.user
        context = _build_context(context_request, base_data=data)
        self.assertIn("autossômico recessivo", context["interpretation_text_rendered"])
        self.assertNotIn("@AR", context["interpretation_text_rendered"])

    def test_update_report_applies_additional_and_secondary_presets_in_rendered_context(self):
        report = Report.objects.create(
            workspace=self.workspace,
            created_by=self.user,
            title="Laudo presets",
            report_type="cancer_hereditario_144",
            data={"laudo_type": "cancer_hereditario_144", **self.defaults},
        )
        request = self.factory.post(
            "/preview/",
            data={
                "additional_findings_mode": "none",
                "additional_findings_obs": "Obs adicional.",
                "secondary_findings_mode": "present",
                "secondary_findings_obs": "Obs secundária.",
            },
        )
        request.user = self.user
        request.workspace = self.workspace

        data = _update_report_from_request(report, request)
        self.assertEqual(data["additional_findings_mode"], "none")
        self.assertEqual(data["secondary_findings_mode"], "present")

        context_request = self.factory.get("/")
        context_request.user = self.user
        context = _build_context(context_request, base_data=data)
        self.assertIn("Nao foram identificados achados adicionais", context["additional_findings_text_rendered"])
        self.assertTrue(context["additional_findings_text_rendered"].endswith("Obs adicional."))
        self.assertIn("variantes clinicamente acionaveis", context["secondary_findings_text_rendered"])
        self.assertTrue(context["secondary_findings_text_rendered"].endswith("Obs secundária."))

    def test_update_report_applies_recommendations_mode_and_obs_in_rendered_context(self):
        report = Report.objects.create(
            workspace=self.workspace,
            created_by=self.user,
            title="Laudo recomendacoes",
            report_type="cancer_hereditario_144",
            data={"laudo_type": "cancer_hereditario_144", **self.defaults},
        )
        request = self.factory.post(
            "/preview/",
            data={
                "recommendations_mode": "without_main_finding",
                "recommendations_obs": "Obs final.",
            },
        )
        request.user = self.user
        request.workspace = self.workspace

        data = _update_report_from_request(report, request)
        self.assertEqual(data["recommendations_mode"], "without_main_finding")

        context_request = self.factory.get("/")
        context_request.user = self.user
        context = _build_context(context_request, base_data=data)
        self.assertIn("aconselhamento genetico", context["recommendations_text_rendered"])
        self.assertTrue(context["recommendations_text_rendered"].endswith("Obs final."))

    def test_update_report_keeps_raw_additional_text_when_observation_is_filled(self):
        report = Report.objects.create(
            workspace=self.workspace,
            created_by=self.user,
            title="Laudo observacao",
            report_type="cancer_hereditario_144",
            data={"laudo_type": "cancer_hereditario_144", **self.defaults},
        )
        request = self.factory.post(
            "/preview/",
            data={
                "additional_findings_mode": "manual",
                "additional_findings_text": "Texto base adicional.",
                "additional_findings_obs": "Paz e amor",
            },
        )
        request.user = self.user
        request.workspace = self.workspace

        data = _update_report_from_request(report, request)
        self.assertEqual(data["additional_findings_text"], "Texto base adicional.")

        context_request = self.factory.get("/")
        context_request.user = self.user
        context = _build_context(context_request, base_data=data)
        self.assertTrue(context["additional_findings_text_rendered"].endswith("Paz e amor"))

    def test_update_report_clears_legacy_appended_additional_observation(self):
        report = Report.objects.create(
            workspace=self.workspace,
            created_by=self.user,
            title="Laudo obs legada",
            report_type="cancer_hereditario_144",
            data={
                "laudo_type": "cancer_hereditario_144",
                **self.defaults,
                "additional_findings_text": "Texto base adicional.\n\nPaz e amor\n\nPaz e amor",
                "additional_findings_obs": "Paz e amor",
            },
        )
        request = self.factory.post(
            "/preview/",
            data={
                "additional_findings_mode": "manual",
                "additional_findings_text": "Texto base adicional.\n\nPaz e amor\n\nPaz e amor",
                "additional_findings_obs": "",
            },
        )
        request.user = self.user
        request.workspace = self.workspace

        data = _update_report_from_request(report, request)
        self.assertEqual(data["additional_findings_text"], "Texto base adicional.")

    def test_update_report_cleans_repeated_legacy_tail_when_obs_already_empty(self):
        report = Report.objects.create(
            workspace=self.workspace,
            created_by=self.user,
            title="Laudo obs legada sem historico",
            report_type="cancer_hereditario_144",
            data={
                "laudo_type": "cancer_hereditario_144",
                **self.defaults,
                "additional_findings_text": "Paz e amor\n\nPaz e amor\n\nPaz e amor",
                "additional_findings_obs": "",
            },
        )
        request = self.factory.post(
            "/preview/",
            data={
                "additional_findings_mode": "manual",
                "additional_findings_text": "Paz e amor\n\nPaz e amor\n\nPaz e amor",
                "additional_findings_obs": "",
            },
        )
        request.user = self.user
        request.workspace = self.workspace

        data = _update_report_from_request(report, request)
        self.assertEqual(data["additional_findings_text"], "")

    def test_build_context_parses_variant_and_cnv_table_rows(self):
        request = self.factory.get("/")
        request.user = self.user
        context = _build_context(
            request,
            base_data={
                "laudo_type": "cancer_hereditario_144",
                "main_gene": "GAA",
                "main_transcript": "NM_000152.5",
                "main_variant_c": "c.2560C>T",
                "main_variant_p": "p.(Arg854*)",
                "main_dbsnp": "rs121907943",
                "main_zygosity": "Heterozigose",
                "main_inheritance": "Autossômica recessiva",
                "main_classification": "Patogênica",
                "main_condition": "Doença de Pompe (OMIM:#232300)",
                "main_variant_extra_rows_text": "GAA; NM_000152.5; c.-32-13T>G; p.(?); rs386834236; Heterozigose; Autossômica recessiva; Patogênica; Doença de Pompe tardia",
                "main_cnv_rows_text": "Deleção; chr1:93270347-103006350; 1p22.1-p21.1; Heterozigose; VUS",
                "secondary_variant_rows_text": "MYBPC3; NM_000256.3; c.3065G>C; p.(Arg1022Pro); rs397516000; Heterozigose; Autossômica dominante; Patogênica; Cardiomiopatia",
            },
        )

        self.assertEqual(len(context["main_variant_rows"]), 2)
        self.assertEqual(context["main_variant_rows"][1]["variant_c"], "c.-32-13T>G")
        self.assertEqual(len(context["main_cnv_rows"]), 1)
        self.assertEqual(context["main_cnv_rows"][0]["coordinate"], "chr1:93270347-103006350")
        self.assertEqual(len(context["secondary_variant_rows"]), 1)
        self.assertEqual(context["secondary_variant_rows"][0]["gene"], "MYBPC3")

    def test_interpretation_supports_table_tokens_for_first_and_second_rows(self):
        request = self.factory.get("/")
        request.user = self.user
        context = _build_context(
            request,
            base_data={
                "laudo_type": "cancer_hereditario_144",
                "main_gene": "GAA",
                "main_variant_c": "c.2560C>T",
                "main_variant_extra_rows_text": "GAA; NM_000152.5; c.-32-13T>G; p.(?); rs386834236; Heterozigose; Autossômica recessiva; Patogênica; Doença de Pompe tardia",
                "interpretation_text": "Primeira: @GENE @VAR_C. Segunda: @GENE2 @VAR_C2.",
            },
        )

        self.assertIn("Primeira: GAA c.2560C>T.", context["interpretation_text_rendered"])
        self.assertIn("Segunda: GAA c.-32-13T>G.", context["interpretation_text_rendered"])

    def test_update_report_normalizes_metrics_mode_fields(self):
        report = Report.objects.create(
            workspace=self.workspace,
            created_by=self.user,
            title="Laudo metricas exoma",
            report_type="cancer_hereditario_144",
            data={"laudo_type": "cancer_hereditario_144", **self.defaults},
        )
        request = self.factory.post(
            "/preview/",
            data={
                "metrics_mode": "exome_mito",
                "metrics_nuclear_base": "30",
                "metrics_nuclear_percent": "90,42%",
                "metrics_mito_base": "100",
                "metrics_mito_percent": "98,45%",
            },
        )
        request.user = self.user
        request.workspace = self.workspace

        data = _update_report_from_request(report, request)
        self.assertEqual(data["metrics_mode"], "exome_mito")
        self.assertEqual(data["metrics_nuclear_base"], "30x")
        self.assertEqual(data["metrics_mito_base"], "100x")
        self.assertEqual(data["metrics_nuclear_percent"], "90,42%")
        self.assertEqual(data["metrics_mito_percent"], "98,45%")
