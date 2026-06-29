import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  CircularProgress,
  FormControl,
  FormHelperText,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  Step,
  StepLabel,
  Stepper,
  TextField,
  Typography,
} from "@mui/material";
import UploadFileOutlined from "@mui/icons-material/UploadFileOutlined";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { apiFetch, ApiError } from "../api/http";
import { currentTaxPeriod, formatTaxPeriod, formatTaxPeriodShort } from "../lib/reconciliationCases";

type Client = {
  id: number;
  client_name: string;
  purchase_system_type: string;
};

type ProcessContext = {
  active_gstr2b_mapping: { id: number; mapping_name: string; version: string } | null;
  purchase_register_mappings: { id: number; mapping_name: string; source: string }[];
  suggested_pr_mapping_id: number | null;
  client_purchase_system_type: string | null;
};

type CaseDetail = {
  id: number;
  case_name: string;
  client_id: number | null;
  tax_period_month: number;
  tax_period_year: number;
  status: string;
  gstr2b_original_filename: string | null;
  pr_original_filename: string | null;
  pr_mapping_id: number | null;
  process_context: ProcessContext | null;
};

const STEPS = ["Case Details", "Upload Files", "Confirm Mappings", "Process Reconciliation", "Review Results"];
const ACCEPTED_EXTENSIONS = [".xls", ".xlsx"];
const MONTH_OPTIONS = Array.from({ length: 12 }, (_, i) => i + 1);

function isAcceptedExcel(file: File): boolean {
  const name = file.name.toLowerCase();
  return ACCEPTED_EXTENSIONS.some((ext) => name.endsWith(ext));
}

export function ReconciliationCaseFormPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const isEdit = Boolean(id);
  const caseId = id ? Number(id) : null;

  const defaultPeriod = currentTaxPeriod();
  const [activeStep, setActiveStep] = useState(0);
  const [caseName, setCaseName] = useState("");
  const [clientId, setClientId] = useState<number | "">("");
  const [taxMonth, setTaxMonth] = useState(defaultPeriod.month);
  const [taxYear, setTaxYear] = useState(defaultPeriod.year);
  const [gstr2bFile, setGstr2bFile] = useState<File | null>(null);
  const [prFile, setPrFile] = useState<File | null>(null);
  const [existingGstr2b, setExistingGstr2b] = useState<string | null>(null);
  const [existingPr, setExistingPr] = useState<string | null>(null);
  const [prMappingId, setPrMappingId] = useState<number | "">("");
  const [detailsError, setDetailsError] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [mappingError, setMappingError] = useState<string | null>(null);
  const [processError, setProcessError] = useState<string | null>(null);
  const [savedCaseId, setSavedCaseId] = useState<number | null>(caseId);
  const [reprocessConfirm, setReprocessConfirm] = useState(false);

  const clientsQ = useQuery({
    queryKey: ["clients-for-cases"],
    queryFn: () => apiFetch<Client[]>("/app/clients"),
  });

  const caseQ = useQuery({
    queryKey: ["reconciliation-case", caseId],
    queryFn: () => apiFetch<CaseDetail>(`/app/reconciliation-cases/${caseId}`),
    enabled: isEdit && Boolean(caseId),
  });

  const savedCaseQ = useQuery({
    queryKey: ["reconciliation-case", savedCaseId],
    queryFn: () => apiFetch<CaseDetail>(`/app/reconciliation-cases/${savedCaseId}`),
    enabled: Boolean(savedCaseId) && activeStep >= 2,
  });

  const activeCaseData = caseQ.data ?? savedCaseQ.data;
  const processContext = activeCaseData?.process_context;
  const activeGstr2b = processContext?.active_gstr2b_mapping;
  const prMappings = processContext?.purchase_register_mappings ?? [];

  useEffect(() => {
    if (!caseQ.data) return;
    const c = caseQ.data;
    setCaseName(c.case_name);
    setClientId(c.client_id ?? "");
    setTaxMonth(c.tax_period_month);
    setTaxYear(c.tax_period_year);
    setExistingGstr2b(c.gstr2b_original_filename);
    setExistingPr(c.pr_original_filename);
    setPrMappingId(c.pr_mapping_id ?? c.process_context?.suggested_pr_mapping_id ?? "");
    setSavedCaseId(c.id);
    if (c.status === "processed" || c.status === "completed") {
      setActiveStep(4);
    } else if (c.gstr2b_original_filename && c.pr_original_filename) {
      setActiveStep(2);
    }
  }, [caseQ.data]);

  useEffect(() => {
    if (!savedCaseQ.data?.process_context?.suggested_pr_mapping_id) return;
    if (prMappingId === "") {
      setPrMappingId(savedCaseQ.data.process_context.suggested_pr_mapping_id ?? "");
    }
  }, [savedCaseQ.data, prMappingId]);

  const detailsValid = caseName.trim().length > 0 && taxMonth >= 1 && taxMonth <= 12 && taxYear >= 2000;
  const uploadValid = Boolean(gstr2bFile || existingGstr2b) && Boolean(prFile || existingPr);

  const buildFormData = (includeFiles: boolean) => {
    const form = new FormData();
    form.append("case_name", caseName.trim());
    form.append("tax_period_month", String(taxMonth));
    form.append("tax_period_year", String(taxYear));
    if (clientId !== "") form.append("client_id", String(clientId));
    if (prMappingId !== "") form.append("pr_mapping_id", String(prMappingId));
    if (includeFiles) {
      if (gstr2bFile) form.append("gstr2b_file", gstr2bFile);
      if (prFile) form.append("purchase_register_file", prFile);
    }
    return form;
  };

  const saveMutation = useMutation({
    mutationFn: async () => {
      const form = buildFormData(true);
      if (savedCaseId) {
        return apiFetch<CaseDetail>(`/app/reconciliation-cases/${savedCaseId}`, { method: "PATCH", body: form });
      }
      return apiFetch<CaseDetail>("/app/reconciliation-cases", { method: "POST", body: form });
    },
    onSuccess: (data) => {
      setSavedCaseId(data.id);
      setExistingGstr2b(data.gstr2b_original_filename);
      setExistingPr(data.pr_original_filename);
      if (data.pr_mapping_id) setPrMappingId(data.pr_mapping_id);
    },
  });

  const processMutation = useMutation({
    mutationFn: async () => {
      const idToUse = savedCaseId;
      if (!idToUse) throw new Error("Case not saved");
      const params = prMappingId !== "" ? `?pr_mapping_id=${prMappingId}` : "";
      return apiFetch<CaseDetail>(`/app/reconciliation-cases/${idToUse}/process${params}`, { method: "POST" });
    },
  });

  const handleNextFromDetails = async () => {
    setDetailsError(null);
    if (!detailsValid) {
      setDetailsError("Case Name and Tax Period are required.");
      return;
    }
    setActiveStep(1);
  };

  const handleNextFromUpload = async () => {
    setUploadError(null);
    if (!uploadValid) {
      setUploadError("Both GSTR-2B and Purchase Register files are required.");
      return;
    }
    if (gstr2bFile && !isAcceptedExcel(gstr2bFile)) {
      setUploadError("GSTR-2B file must be .xls or .xlsx.");
      return;
    }
    if (prFile && !isAcceptedExcel(prFile)) {
      setUploadError("Purchase Register file must be .xls or .xlsx.");
      return;
    }
    try {
      await saveMutation.mutateAsync();
      await savedCaseQ.refetch();
      setActiveStep(2);
    } catch (err) {
      setUploadError(err instanceof ApiError ? err.message : "Failed to save files");
    }
  };

  const handleNextFromMappings = () => {
    setMappingError(null);
    if (!activeGstr2b) {
      setMappingError("No active GSTR-2B mapping exists. Configure and activate one in Data Mapping → GSTR-2B.");
      return;
    }
    if (!prMappingId) {
      setMappingError("Select a Purchase Register mapping before processing.");
      return;
    }
    if (prMappings.length === 0) {
      setMappingError("No Purchase Register mapping exists for the selected client source.");
      return;
    }
    setActiveStep(3);
  };

  const handleProcess = async () => {
    setProcessError(null);
    const needsConfirm =
      isEdit && (caseQ.data?.status === "processed" || caseQ.data?.status === "completed") && !reprocessConfirm;
    if (needsConfirm) {
      setReprocessConfirm(true);
      return;
    }
    try {
      await processMutation.mutateAsync();
      setActiveStep(4);
      setReprocessConfirm(false);
    } catch (err) {
      setProcessError(err instanceof ApiError ? err.message : "Processing failed");
    }
  };

  const title = isEdit ? "Edit Reconciliation Case" : "New Reconciliation Case";
  const isProcessing = processMutation.isPending || saveMutation.isPending;

  const prMappingOptions = useMemo(() => {
    if (!processContext?.client_purchase_system_type) return prMappings;
    const filtered = prMappings.filter((m) => m.source === processContext.client_purchase_system_type);
    return filtered.length > 0 ? filtered : prMappings;
  }, [prMappings, processContext?.client_purchase_system_type]);

  return (
    <Box maxWidth={900}>
      <Typography variant="h5" fontWeight={600} mb={1}>
        {title}
      </Typography>
      <Typography color="text.secondary" mb={3}>
        Upload GSTR-2B and Purchase Register files, confirm mappings, and run reconciliation.
      </Typography>

      <Stepper activeStep={activeStep} alternativeLabel sx={{ mb: 4 }}>
        {STEPS.map((label) => (
          <Step key={label}>
            <StepLabel>{label}</StepLabel>
          </Step>
        ))}
      </Stepper>

      {activeStep === 0 && (
        <Card variant="outlined">
          <CardContent>
            <Stack spacing={2}>
              <TextField
                label="Case Name"
                value={caseName}
                onChange={(e) => setCaseName(e.target.value)}
                required
                fullWidth
              />
              <FormControl fullWidth>
                <InputLabel>Client (optional)</InputLabel>
                <Select
                  label="Client (optional)"
                  value={clientId}
                  onChange={(e) => {
                    const val = e.target.value;
                    setClientId(val === "" ? "" : Number(val));
                    setPrMappingId("");
                  }}
                >
                  <MenuItem value="">None</MenuItem>
                  {clientsQ.data?.map((c) => (
                    <MenuItem key={c.id} value={c.id}>
                      {c.client_name}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
              <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
                <FormControl fullWidth required>
                  <InputLabel>Tax Period Month</InputLabel>
                  <Select
                    label="Tax Period Month"
                    value={taxMonth}
                    onChange={(e) => setTaxMonth(Number(e.target.value))}
                  >
                    {MONTH_OPTIONS.map((m) => (
                      <MenuItem key={m} value={m}>
                        {formatTaxPeriod(m, taxYear).split(" ")[0]}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
                <TextField
                  label="Tax Period Year"
                  type="number"
                  value={taxYear}
                  onChange={(e) => setTaxYear(Number(e.target.value))}
                  required
                  fullWidth
                  inputProps={{ min: 2000, max: 2100 }}
                />
              </Stack>
              <Alert severity="info">
                Tax Period: <strong>{formatTaxPeriod(taxMonth, taxYear)}</strong> ({formatTaxPeriodShort(taxMonth, taxYear)})
              </Alert>
              {detailsError && <Alert severity="error">{detailsError}</Alert>}
              <Stack direction="row" justifyContent="flex-end">
                <Button variant="contained" onClick={handleNextFromDetails}>
                  Next
                </Button>
              </Stack>
            </Stack>
          </CardContent>
        </Card>
      )}

      {activeStep === 1 && (
        <Card variant="outlined">
          <CardContent>
            <Stack spacing={3}>
              <Box>
                <Typography fontWeight={600} mb={1}>
                  GSTR-2B File
                </Typography>
                {existingGstr2b && !gstr2bFile && (
                  <Typography variant="body2" color="text.secondary" mb={1}>
                    Current file: {existingGstr2b}
                  </Typography>
                )}
                <Button variant="outlined" component="label" startIcon={<UploadFileOutlined />}>
                  {gstr2bFile ? gstr2bFile.name : "Upload GSTR-2B (.xls / .xlsx)"}
                  <input
                    hidden
                    type="file"
                    accept=".xls,.xlsx"
                    onChange={(e) => setGstr2bFile(e.target.files?.[0] ?? null)}
                  />
                </Button>
              </Box>
              <Box>
                <Typography fontWeight={600} mb={1}>
                  Purchase Register File
                </Typography>
                {existingPr && !prFile && (
                  <Typography variant="body2" color="text.secondary" mb={1}>
                    Current file: {existingPr}
                  </Typography>
                )}
                <Button variant="outlined" component="label" startIcon={<UploadFileOutlined />}>
                  {prFile ? prFile.name : "Upload Purchase Register (.xls / .xlsx)"}
                  <input
                    hidden
                    type="file"
                    accept=".xls,.xlsx"
                    onChange={(e) => setPrFile(e.target.files?.[0] ?? null)}
                  />
                </Button>
              </Box>
              {uploadError && <Alert severity="error">{uploadError}</Alert>}
              <Stack direction="row" justifyContent="space-between">
                <Button onClick={() => setActiveStep(0)}>Back</Button>
                <Button variant="contained" onClick={handleNextFromUpload} disabled={isProcessing}>
                  {isProcessing ? <CircularProgress size={22} /> : "Next"}
                </Button>
              </Stack>
            </Stack>
          </CardContent>
        </Card>
      )}

      {activeStep === 2 && (
        <Card variant="outlined">
          <CardContent>
            <Stack spacing={2}>
              <Box>
                <Typography fontWeight={600}>GSTR-2B Mapping</Typography>
                {activeGstr2b ? (
                  <Typography variant="body2" mt={0.5}>
                    {activeGstr2b.mapping_name} (v{activeGstr2b.version}) — active
                  </Typography>
                ) : (
                  <Alert severity="warning" sx={{ mt: 1 }}>
                    No active GSTR-2B mapping. Create and activate one under Data Mapping → GSTR-2B.
                  </Alert>
                )}
              </Box>
              <FormControl fullWidth required error={!prMappingId && Boolean(mappingError)}>
                <InputLabel>Purchase Register Mapping</InputLabel>
                <Select
                  label="Purchase Register Mapping"
                  value={prMappingId}
                  onChange={(e) => setPrMappingId(Number(e.target.value))}
                >
                  {prMappingOptions.map((m) => (
                    <MenuItem key={m.id} value={m.id}>
                      {m.mapping_name} ({m.source})
                    </MenuItem>
                  ))}
                </Select>
                {prMappingOptions.length === 0 && (
                  <FormHelperText>No Purchase Register mappings available for this client source.</FormHelperText>
                )}
              </FormControl>
              <Typography variant="body2" color="text.secondary">
                GSTR-2B file: {existingGstr2b ?? gstr2bFile?.name ?? "—"}
                <br />
                Purchase Register file: {existingPr ?? prFile?.name ?? "—"}
              </Typography>
              {mappingError && <Alert severity="error">{mappingError}</Alert>}
              <Stack direction="row" justifyContent="space-between">
                <Button onClick={() => setActiveStep(1)}>Back</Button>
                <Button variant="contained" onClick={handleNextFromMappings}>
                  Next
                </Button>
              </Stack>
            </Stack>
          </CardContent>
        </Card>
      )}

      {activeStep === 3 && (
        <Card variant="outlined">
          <CardContent>
            <Stack spacing={2}>
              <Typography>
                Ready to process reconciliation for <strong>{caseName}</strong> ({formatTaxPeriod(taxMonth, taxYear)}).
              </Typography>
              {reprocessConfirm && (
                <Alert severity="warning">
                  Existing processed results will be replaced. Click Process again to confirm.
                </Alert>
              )}
              {processError && <Alert severity="error">{processError}</Alert>}
              <Stack direction="row" justifyContent="space-between">
                <Button onClick={() => setActiveStep(2)} disabled={isProcessing}>
                  Back
                </Button>
                <Button variant="contained" onClick={handleProcess} disabled={isProcessing}>
                  {isProcessing ? (
                    <>
                      <CircularProgress size={20} sx={{ mr: 1 }} /> Processing…
                    </>
                  ) : (
                    "Process Reconciliation"
                  )}
                </Button>
              </Stack>
            </Stack>
          </CardContent>
        </Card>
      )}

      {activeStep === 4 && savedCaseId && (
        <Card variant="outlined">
          <CardContent>
            <Stack spacing={2}>
              <Alert severity="success">Reconciliation processed successfully.</Alert>
              <Stack direction="row" spacing={2}>
                <Button variant="contained" onClick={() => navigate(`/app/cases/${savedCaseId}`)}>
                  View Results
                </Button>
                <Button onClick={() => navigate("/app/cases")}>Back to Cases</Button>
              </Stack>
            </Stack>
          </CardContent>
        </Card>
      )}
    </Box>
  );
}
