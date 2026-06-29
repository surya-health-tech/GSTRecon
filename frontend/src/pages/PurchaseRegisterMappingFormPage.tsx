import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  FormControl,
  FormHelperText,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  Step,
  StepLabel,
  Stepper,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from "@mui/material";
import UploadFileOutlined from "@mui/icons-material/UploadFileOutlined";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { apiFetch, ApiError } from "../api/http";
import {
  autoMatchColumns,
  findDuplicateColumnMappings,
  type MatchConfidence,
} from "../lib/columnAutoMatch";

type MasterFieldSummary = {
  id: number;
  field_name: string;
  field_code: string;
  is_required: boolean;
  display_order: number;
};

type MappingDetail = {
  id: number;
  mapping_name: string;
  source: string;
  sheet_name: string | null;
  original_filename: string | null;
  excel_columns: string[];
  sample_row: Record<string, string>;
  column_mappings: Record<string, string>;
};

type ExcelParseResult = {
  sheets: string[];
  sheet_name: string;
  columns: string[];
  sample_row: Record<string, string>;
  master_fields: MasterFieldSummary[];
  suggested_mappings: Record<string, string | null>;
  auto_match_confidence: Record<string, MatchConfidence>;
};

const SOURCE_OPTIONS = [
  { value: "zoho", label: "Zoho" },
  { value: "wings_erp", label: "Wings ERP" },
  { value: "erpnext", label: "ERPNext" },
  { value: "other", label: "Other" },
] as const;

const STEPS = ["Mapping Details", "Upload Excel", "Review Mapping", "Save"];

const ACCEPTED_EXTENSIONS = [".xls", ".xlsx"];

function isAcceptedExcel(file: File): boolean {
  const name = file.name.toLowerCase();
  return ACCEPTED_EXTENSIONS.some((ext) => name.endsWith(ext));
}

export function PurchaseRegisterMappingFormPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const isEdit = Boolean(id);
  const mappingId = id ? Number(id) : null;

  const [activeStep, setActiveStep] = useState(0);
  const [mappingName, setMappingName] = useState("");
  const [source, setSource] = useState("");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [existingFilename, setExistingFilename] = useState<string | null>(null);
  const [sheets, setSheets] = useState<string[]>([]);
  const [selectedSheet, setSelectedSheet] = useState("");
  const [columns, setColumns] = useState<string[]>([]);
  const [sampleRow, setSampleRow] = useState<Record<string, string>>({});
  const [masterFields, setMasterFields] = useState<MasterFieldSummary[]>([]);
  const [mappings, setMappings] = useState<Record<string, string | null>>({});
  const [confidence, setConfidence] = useState<Record<string, MatchConfidence>>({});
  const [detailsError, setDetailsError] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [reviewError, setReviewError] = useState<string | null>(null);
  const [lowMatchWarning, setLowMatchWarning] = useState(false);

  const masterFieldsQ = useQuery({
    queryKey: ["master-fields-for-pr-mapping"],
    queryFn: async () => {
      const fields = await apiFetch<
        { field_name: string; field_code: string; is_required: boolean; display_order: number; applicable_source: string; is_active: boolean }[]
      >("/app/data-mapping/master-fields?is_active=true");
      return fields
        .filter((f) => f.applicable_source === "purchase_register" || f.applicable_source === "both")
        .map((f, idx) => ({
          id: idx,
          field_name: f.field_name,
          field_code: f.field_code,
          is_required: f.is_required,
          display_order: f.display_order,
        }));
    },
  });

  useEffect(() => {
    if (masterFieldsQ.data && masterFieldsQ.data.length > 0 && masterFields.length === 0) {
      setMasterFields(masterFieldsQ.data);
    }
  }, [masterFieldsQ.data, masterFields.length]);

  const detailQ = useQuery({
    queryKey: ["purchase-register-mapping", mappingId],
    queryFn: () => apiFetch<MappingDetail>(`/app/data-mapping/purchase-register-mappings/${mappingId}`),
    enabled: isEdit && mappingId != null && !Number.isNaN(mappingId),
  });

  useEffect(() => {
    if (!detailQ.data) return;
    const row = detailQ.data;
    setMappingName(row.mapping_name);
    setSource(row.source);
    setExistingFilename(row.original_filename);
    setSelectedSheet(row.sheet_name ?? "");
    setColumns(row.excel_columns);
    setSampleRow(row.sample_row);
    const fieldMappings: Record<string, string | null> = {};
    for (const [code, col] of Object.entries(row.column_mappings)) {
      fieldMappings[code] = col;
    }
    setMappings(fieldMappings);
  }, [detailQ.data]);

  const parseMutation = useMutation({
    mutationFn: async ({ file, sheet }: { file: File; sheet?: string }) => {
      const form = new FormData();
      form.append("file", file);
      if (sheet) form.append("sheet_name", sheet);
      return apiFetch<ExcelParseResult>("/app/data-mapping/purchase-register-mappings/parse-excel", {
        method: "POST",
        body: form,
      });
    },
    onSuccess: (data) => {
      setSheets(data.sheets);
      setSelectedSheet(data.sheet_name);
      setColumns(data.columns);
      setSampleRow(data.sample_row);
      setMasterFields(data.master_fields);
      setMappings(data.suggested_mappings);
      setConfidence(data.auto_match_confidence);
      setLowMatchWarning(
        Object.values(data.auto_match_confidence).some((c) => c === "low" || c === "none"),
      );
      setUploadError(null);
      setActiveStep(2);
    },
    onError: (err) => {
      setUploadError(err instanceof ApiError ? err.message : "Could not parse Excel file");
    },
  });

  const saveMutation = useMutation({
    mutationFn: async () => {
      const columnMappings = Object.fromEntries(
        Object.entries(mappings).filter((entry): entry is [string, string] => Boolean(entry[1])),
      );

      if (!isEdit) {
        if (!uploadFile) throw new Error("Excel file is required");
        const form = new FormData();
        form.append("mapping_name", mappingName.trim());
        form.append("source", source);
        form.append("sheet_name", selectedSheet);
        form.append("column_mappings", JSON.stringify(columnMappings));
        form.append("file", uploadFile);
        return apiFetch<MappingDetail>("/app/data-mapping/purchase-register-mappings", {
          method: "POST",
          body: form,
        });
      }

      if (uploadFile) {
        const form = new FormData();
        form.append("mapping_name", mappingName.trim());
        form.append("source", source);
        form.append("sheet_name", selectedSheet);
        form.append("column_mappings", JSON.stringify(columnMappings));
        form.append("file", uploadFile);
        return apiFetch<MappingDetail>(`/app/data-mapping/purchase-register-mappings/${mappingId}`, {
          method: "PATCH",
          body: form,
        });
      }

      return apiFetch<MappingDetail>(`/app/data-mapping/purchase-register-mappings/${mappingId}`, {
        method: "PATCH",
        body: JSON.stringify({
          mapping_name: mappingName.trim(),
          source,
          sheet_name: selectedSheet || null,
          column_mappings: columnMappings,
          excel_columns: columns,
          sample_row: sampleRow,
        }),
      });
    },
    onSuccess: () => {
      navigate("/app/data-mapping/purchase-register?saved=1");
    },
    onError: (err) => {
      setReviewError(err instanceof ApiError ? err.message : "Could not save mapping");
      setActiveStep(2);
    },
  });

  const sortedFields = useMemo(
    () => [...masterFields].sort((a, b) => a.display_order - b.display_order || a.field_name.localeCompare(b.field_name)),
    [masterFields],
  );

  const fieldsForReview = useMemo(() => {
    if (sortedFields.length > 0) return sortedFields;
    return Object.keys(mappings).map((code, idx) => ({
      id: idx,
      field_code: code,
      field_name: code.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
      is_required: true,
      display_order: idx,
    }));
  }, [sortedFields, mappings]);

  const validateDetails = (): boolean => {
    if (!mappingName.trim()) {
      setDetailsError("Mapping name is required.");
      return false;
    }
    if (!source) {
      setDetailsError("Purchase register source is required.");
      return false;
    }
    setDetailsError(null);
    return true;
  };

  const validateUpload = (): boolean => {
    if (!isEdit && !uploadFile) {
      setUploadError("Excel file is required when creating a new mapping.");
      return false;
    }
    if (isEdit && !uploadFile && columns.length === 0) {
      setUploadError("Upload an Excel file or keep the existing file mapping.");
      return false;
    }
    setUploadError(null);
    return true;
  };

  const validateReview = (): boolean => {
    const duplicateMsg = findDuplicateColumnMappings(mappings);
    if (duplicateMsg) {
      setReviewError(duplicateMsg);
      return false;
    }

    const missingRequired = fieldsForReview
      .filter((f) => f.is_required && !mappings[f.field_code])
      .map((f) => f.field_name);

    if (missingRequired.length > 0) {
      setReviewError(`Required master fields must be mapped: ${missingRequired.join(", ")}`);
      return false;
    }

    setReviewError(null);
    return true;
  };

  const applyParseResult = (data: ExcelParseResult) => {
    setSheets(data.sheets);
    setSelectedSheet(data.sheet_name);
    setColumns(data.columns);
    setSampleRow(data.sample_row);
    setMasterFields(data.master_fields);
    setMappings(data.suggested_mappings);
    setConfidence(data.auto_match_confidence);
    setLowMatchWarning(Object.values(data.auto_match_confidence).some((c) => c === "low" || c === "none"));
  };

  const handleSheetChange = async (sheet: string) => {
    setSelectedSheet(sheet);
    if (!uploadFile) return;
    setUploadError(null);
    try {
      const form = new FormData();
      form.append("file", uploadFile);
      form.append("sheet_name", sheet);
      const data = await apiFetch<ExcelParseResult>(
        "/app/data-mapping/purchase-register-mappings/parse-excel",
        { method: "POST", body: form },
      );
      applyParseResult(data);
    } catch (err) {
      setUploadError(err instanceof ApiError ? err.message : "Could not parse selected sheet");
    }
  };

  const handleResetAutoMapping = () => {
    const fieldCodes = fieldsForReview.map((f) => f.field_code);
    const { mappings: next, confidence: nextConf } = autoMatchColumns(fieldCodes, columns);
    setMappings(next);
    setConfidence(nextConf);
    setLowMatchWarning(Object.values(nextConf).some((c) => c === "low" || c === "none"));
    setReviewError(null);
  };

  const handleMappingChange = (fieldCode: string, column: string) => {
    const value = column || null;
    setMappings((prev) => ({ ...prev, [fieldCode]: value }));
    setReviewError(null);
  };

  const goNext = () => {
    if (activeStep === 0) {
      if (!validateDetails()) return;
      setActiveStep(1);
      return;
    }
    if (activeStep === 1) {
      if (!validateUpload()) return;
      if (uploadFile && columns.length === 0) {
        parseMutation.mutate({ file: uploadFile, sheet: selectedSheet || undefined });
      } else {
        setActiveStep(2);
      }
      return;
    }
    if (activeStep === 2) {
      if (!validateReview()) return;
      setActiveStep(3);
    }
  };

  const handleSave = () => {
    if (!validateDetails() || !validateReview()) return;
    if (!isEdit && !uploadFile) {
      setUploadError("Excel file is required.");
      setActiveStep(1);
      return;
    }
    setReviewError(null);
    saveMutation.mutate();
  };

  if (isEdit && detailQ.isLoading) {
    return (
      <Box py={4}>
        <Typography color="text.secondary">Loading mapping…</Typography>
      </Box>
    );
  }

  if (isEdit && detailQ.isError) {
    return (
      <Alert severity="error">
        {detailQ.error instanceof ApiError ? detailQ.error.message : "Failed to load mapping"}
      </Alert>
    );
  }

  return (
    <Box>
      <Typography variant="h5" fontWeight={600} mb={1}>
        {isEdit ? "Edit Purchase Register Mapping" : "Create Purchase Register Mapping"}
      </Typography>
      <Typography color="text.secondary" mb={3}>
        Configure how purchase register Excel columns map to reconciliation master fields.
      </Typography>

      <Stepper activeStep={activeStep} sx={{ mb: 3 }}>
        {STEPS.map((label) => (
          <Step key={label}>
            <StepLabel>{label}</StepLabel>
          </Step>
        ))}
      </Stepper>

      {activeStep === 0 && (
        <Card variant="outlined">
          <CardContent>
            <Stack spacing={2} maxWidth={480}>
              <TextField
                label="Mapping Name"
                value={mappingName}
                onChange={(e) => {
                  setMappingName(e.target.value);
                  setDetailsError(null);
                }}
                required
                fullWidth
              />
              <FormControl fullWidth required error={Boolean(detailsError && !source)}>
                <InputLabel>Purchase Register Source</InputLabel>
                <Select
                  label="Purchase Register Source"
                  value={source}
                  onChange={(e) => {
                    setSource(e.target.value);
                    setDetailsError(null);
                  }}
                >
                  {SOURCE_OPTIONS.map((s) => (
                    <MenuItem key={s.value} value={s.value}>
                      {s.label}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
              {detailsError && <Alert severity="error">{detailsError}</Alert>}
            </Stack>
          </CardContent>
        </Card>
      )}

      {activeStep === 1 && (
        <Card variant="outlined">
          <CardContent>
            <Stack spacing={2} maxWidth={560}>
              {isEdit && existingFilename && !uploadFile && (
                <Alert severity="info">
                  Current file: <strong>{existingFilename}</strong>. Upload a new file below to remap columns.
                </Alert>
              )}
              <Button variant="outlined" component="label" startIcon={<UploadFileOutlined />}>
                Choose Excel File
                <input
                  hidden
                  type="file"
                  accept=".xls,.xlsx,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                  onChange={async (e) => {
                    const file = e.target.files?.[0];
                    if (!file) return;
                    if (!isAcceptedExcel(file)) {
                      setUploadError("Please upload a .xls or .xlsx file.");
                      return;
                    }
                    setUploadFile(file);
                    setExistingFilename(file.name);
                    setUploadError(null);
                    try {
                      const form = new FormData();
                      form.append("file", file);
                      const data = await apiFetch<ExcelParseResult>(
                        "/app/data-mapping/purchase-register-mappings/parse-excel",
                        { method: "POST", body: form },
                      );
                      applyParseResult(data);
                    } catch (err) {
                      setUploadError(err instanceof ApiError ? err.message : "Could not parse Excel file");
                    }
                  }}
                />
              </Button>
              {uploadFile && (
                <Typography variant="body2" color="text.secondary">
                  Selected: {uploadFile.name}
                </Typography>
              )}
              {sheets.length > 1 && (
                <FormControl fullWidth>
                  <InputLabel>Worksheet</InputLabel>
                  <Select
                    label="Worksheet"
                    value={selectedSheet}
                    onChange={(e) => handleSheetChange(e.target.value)}
                  >
                    {sheets.map((sheet) => (
                      <MenuItem key={sheet} value={sheet}>
                        {sheet}
                      </MenuItem>
                    ))}
                  </Select>
                  <FormHelperText>Select the sheet that contains purchase register data.</FormHelperText>
                </FormControl>
              )}
              {uploadError && <Alert severity="error">{uploadError}</Alert>}
            </Stack>
          </CardContent>
        </Card>
      )}

      {activeStep === 2 && (
        <Stack spacing={2}>
          {lowMatchWarning && (
            <Alert severity="warning">
              Some columns were not confidently matched. Review highlighted rows and map required fields before saving.
            </Alert>
          )}
          <Stack direction="row" justifyContent="flex-end">
            <Button onClick={handleResetAutoMapping} disabled={columns.length === 0}>
              Reset Auto Mapping
            </Button>
          </Stack>
          <Card variant="outlined">
            <CardContent sx={{ p: 0, "&:last-child": { pb: 0 } }}>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Master Field</TableCell>
                    <TableCell>Purchase Register Column</TableCell>
                    <TableCell>Sample Value</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {fieldsForReview.map((field) => {
                    const selectedCol = mappings[field.field_code] ?? "";
                    const conf = confidence[field.field_code] ?? (selectedCol ? "high" : "none");
                    const lowConf = conf === "low" || (!selectedCol && conf === "none");
                    return (
                      <TableRow
                        key={field.field_code}
                        sx={{
                          bgcolor:
                            !selectedCol && field.is_required
                              ? "rgba(211, 47, 47, 0.06)"
                              : lowConf
                                ? "rgba(237, 108, 2, 0.06)"
                                : undefined,
                        }}
                      >
                        <TableCell>
                          <Stack direction="row" spacing={1} alignItems="center">
                            <Typography variant="body2">
                              {field.field_name}
                              {field.is_required ? " *" : ""}
                            </Typography>
                            {conf === "high" && selectedCol && (
                              <Chip size="small" label="Auto-matched" color="success" variant="outlined" />
                            )}
                            {conf === "low" && (
                              <Chip size="small" label="Low confidence" color="warning" variant="outlined" />
                            )}
                            {!selectedCol && field.is_required && (
                              <Chip size="small" label="Required" color="error" variant="outlined" />
                            )}
                          </Stack>
                        </TableCell>
                        <TableCell sx={{ minWidth: 220 }}>
                          <FormControl fullWidth size="small" error={field.is_required && !selectedCol}>
                            <Select
                              value={selectedCol}
                              displayEmpty
                              onChange={(e) => handleMappingChange(field.field_code, e.target.value)}
                            >
                              <MenuItem value="">
                                <em>Select column</em>
                              </MenuItem>
                              {columns.map((col) => (
                                <MenuItem key={col} value={col}>
                                  {col}
                                </MenuItem>
                              ))}
                            </Select>
                          </FormControl>
                        </TableCell>
                        <TableCell>
                          <Typography variant="body2" color="text.secondary" sx={{ fontFamily: "monospace" }}>
                            {selectedCol ? sampleRow[selectedCol] || "—" : "—"}
                          </Typography>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
          {reviewError && <Alert severity="error">{reviewError}</Alert>}
        </Stack>
      )}

      {activeStep === 3 && (
        <Card variant="outlined">
          <CardContent>
            <Stack spacing={2}>
              <Alert severity="info">Review your mapping summary, then save.</Alert>
              <Typography>
                <strong>Mapping name:</strong> {mappingName}
              </Typography>
              <Typography>
                <strong>Source:</strong> {SOURCE_OPTIONS.find((s) => s.value === source)?.label ?? source}
              </Typography>
              <Typography>
                <strong>File:</strong> {uploadFile?.name ?? existingFilename ?? "—"}
              </Typography>
              <Typography>
                <strong>Sheet:</strong> {selectedSheet || "—"}
              </Typography>
              <Typography>
                <strong>Mapped fields:</strong>{" "}
                {fieldsForReview.filter((f) => mappings[f.field_code]).length} of {fieldsForReview.length}
              </Typography>
              {saveMutation.isError && (
                <Alert severity="error">
                  {saveMutation.error instanceof ApiError
                    ? saveMutation.error.message
                    : "Could not save mapping"}
                </Alert>
              )}
            </Stack>
          </CardContent>
        </Card>
      )}

      <Stack direction="row" justifyContent="space-between" mt={3}>
        <Button onClick={() => navigate("/app/data-mapping/purchase-register")}>Cancel</Button>
        <Stack direction="row" spacing={1}>
          {activeStep > 0 && (
            <Button onClick={() => setActiveStep((s) => s - 1)} disabled={saveMutation.isPending}>
              Back
            </Button>
          )}
          {activeStep < 2 && (
            <Button variant="contained" onClick={goNext} disabled={parseMutation.isPending}>
              {activeStep === 1 && uploadFile ? (parseMutation.isPending ? "Parsing…" : "Continue") : "Continue"}
            </Button>
          )}
          {activeStep === 2 && (
            <Button variant="contained" onClick={goNext}>
              Continue to Save
            </Button>
          )}
          {activeStep === 3 && (
            <Button variant="contained" onClick={handleSave} disabled={saveMutation.isPending}>
              {saveMutation.isPending ? "Saving…" : "Save Mapping"}
            </Button>
          )}
        </Stack>
      </Stack>
    </Box>
  );
}
