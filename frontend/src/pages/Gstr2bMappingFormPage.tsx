import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  FormControl,
  MenuItem,
  Select,
  Stack,
  Step,
  StepLabel,
  Stepper,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Tabs,
  TextField,
  Typography,
} from "@mui/material";
import UploadFileOutlined from "@mui/icons-material/UploadFileOutlined";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { apiFetch, ApiError } from "../api/http";
import type { MatchConfidence } from "../lib/columnAutoMatch";
import {
  autoMatchGstr2bColumns,
  findDuplicateColumnMappingsForTab,
  isFieldRequiredForGstr2b,
} from "../lib/gstr2bAutoMatch";
import { CDNR_TABS, GSTR2B_NA_LABEL, GSTR2B_NA_VALUE, GSTR2B_TABS, NOTE_TYPE_FIELD, isGstr2bMappingSet, isGstr2bNaMapping, serializeGstr2bColumnMappings } from "../lib/gstr2bTabs";

type MasterFieldSummary = {
  id: number;
  field_name: string;
  field_code: string;
  is_required: boolean;
  display_order: number;
};

type TabMapping = {
  found: boolean;
  tab: string;
  excel_sheet_name?: string | null;
  columns: string[];
  sample_row: Record<string, string>;
  column_mappings: Record<string, string | null>;
  auto_match_confidence: Record<string, MatchConfidence>;
};

type MappingDetail = {
  id: number;
  mapping_name: string;
  version: string;
  is_active: boolean;
  original_filename: string | null;
  sheet_mappings: Record<string, TabMapping>;
};

type ParseResult = {
  excel_sheets: string[];
  tabs: Record<string, TabMapping>;
  master_fields: MasterFieldSummary[];
};

const STEPS = ["Mapping Details", "Upload GSTR-2B File", "Review Sheet Mappings", "Save Mapping"];
const ACCEPTED_EXTENSIONS = [".xls", ".xlsx"];

function isAcceptedExcel(file: File): boolean {
  const name = file.name.toLowerCase();
  return ACCEPTED_EXTENSIONS.some((ext) => name.endsWith(ext));
}

function emptyTabMapping(tab: string): TabMapping {
  return {
    found: false,
    tab,
    excel_sheet_name: null,
    columns: [],
    sample_row: {},
    column_mappings: {},
    auto_match_confidence: {},
  };
}

function tabStatus(tab: TabMapping, masterFields: MasterFieldSummary[]): "complete" | "incomplete" | "missing" {
  if (!tab.found) return "missing";
  const dup = findDuplicateColumnMappingsForTab(tab.column_mappings);
  if (dup) return "incomplete";
  for (const field of masterFields) {
    if (isFieldRequiredForGstr2b(field.field_code, field.is_required, tab.column_mappings)) {
      return "incomplete";
    }
  }
  if (CDNR_TABS.has(tab.tab as (typeof GSTR2B_TABS)[number]) && !isGstr2bMappingSet(tab.column_mappings.note_type)) {
    return "incomplete";
  }
  return "complete";
}

export function Gstr2bMappingFormPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const isEdit = Boolean(id);
  const mappingId = id ? Number(id) : null;

  const [activeStep, setActiveStep] = useState(0);
  const [mappingName, setMappingName] = useState("");
  const [version, setVersion] = useState("");
  const [isActive, setIsActive] = useState(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [existingFilename, setExistingFilename] = useState<string | null>(null);
  const [tabMappings, setTabMappings] = useState<Record<string, TabMapping>>(() =>
    Object.fromEntries(GSTR2B_TABS.map((tab) => [tab, emptyTabMapping(tab)])),
  );
  const [masterFields, setMasterFields] = useState<MasterFieldSummary[]>([]);
  const [reviewTab, setReviewTab] = useState<string>(GSTR2B_TABS[0]);
  const [detailsError, setDetailsError] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [reviewError, setReviewError] = useState<string | null>(null);
  const [lowMatchWarning, setLowMatchWarning] = useState(false);

  const masterFieldsQ = useQuery({
    queryKey: ["master-fields-for-gstr2b"],
    queryFn: async () => {
      const fields = await apiFetch<
        {
          field_name: string;
          field_code: string;
          is_required: boolean;
          display_order: number;
          applicable_source: string;
          is_active: boolean;
        }[]
      >("/app/data-mapping/master-fields?is_active=true");
      return fields
        .filter((f) => f.applicable_source === "gstr_2b" || f.applicable_source === "both")
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
    queryKey: ["gstr2b-mapping", mappingId],
    queryFn: () => apiFetch<MappingDetail>(`/app/data-mapping/gstr-2b-mappings/${mappingId}`),
    enabled: isEdit && mappingId != null && !Number.isNaN(mappingId),
  });

  useEffect(() => {
    if (!detailQ.data) return;
    const row = detailQ.data;
    setMappingName(row.mapping_name);
    setVersion(row.version);
    setIsActive(row.is_active);
    setExistingFilename(row.original_filename);
    const loaded: Record<string, TabMapping> = {};
    for (const tab of GSTR2B_TABS) {
      const data = row.sheet_mappings[tab];
      loaded[tab] = data
        ? {
            found: Boolean(data.found),
            tab,
            excel_sheet_name: data.excel_sheet_name,
            columns: data.columns ?? [],
            sample_row: data.sample_row ?? {},
            column_mappings: Object.fromEntries(
              Object.entries(data.column_mappings ?? {}).map(([k, v]) => [k, v ?? null]),
            ),
            auto_match_confidence: data.auto_match_confidence ?? {},
          }
        : emptyTabMapping(tab);
    }
    setTabMappings(loaded);
  }, [detailQ.data]);

  const parseMutation = useMutation({
    mutationFn: async (file: File) => {
      const form = new FormData();
      form.append("file", file);
      return apiFetch<ParseResult>("/app/data-mapping/gstr-2b-mappings/parse-excel", {
        method: "POST",
        body: form,
      });
    },
    onSuccess: (data) => {
      setMasterFields(data.master_fields);
      setTabMappings(data.tabs);
      setLowMatchWarning(
        Object.values(data.tabs).some(
          (t) => t.found && Object.values(t.auto_match_confidence).some((c) => c === "low" || c === "none"),
        ),
      );
      setUploadError(null);
      setActiveStep(2);
    },
    onError: (err) => {
      setUploadError(err instanceof ApiError ? err.message : "Could not parse GSTR-2B file");
    },
  });

  const saveMutation = useMutation({
    mutationFn: async () => {
      const sheetMappingsPayload = Object.fromEntries(
        Object.entries(tabMappings).map(([tab, data]) => [
          tab,
          {
            found: data.found,
            excel_sheet_name: data.excel_sheet_name,
            column_mappings: serializeGstr2bColumnMappings(data.column_mappings),
          },
        ]),
      );

      if (!isEdit) {
        if (!uploadFile) throw new Error("Excel file is required");
        const form = new FormData();
        form.append("mapping_name", mappingName.trim());
        form.append("version", version.trim());
        form.append("sheet_mappings", JSON.stringify(sheetMappingsPayload));
        form.append("file", uploadFile);
        return apiFetch<MappingDetail>("/app/data-mapping/gstr-2b-mappings", { method: "POST", body: form });
      }

      if (uploadFile) {
        const form = new FormData();
        form.append("mapping_name", mappingName.trim());
        form.append("version", version.trim());
        form.append("sheet_mappings", JSON.stringify(sheetMappingsPayload));
        form.append("file", uploadFile);
        return apiFetch<MappingDetail>(`/app/data-mapping/gstr-2b-mappings/${mappingId}`, {
          method: "PATCH",
          body: form,
        });
      }

      return apiFetch<MappingDetail>(`/app/data-mapping/gstr-2b-mappings/${mappingId}`, {
        method: "PATCH",
        body: JSON.stringify({
          mapping_name: mappingName.trim(),
          version: version.trim(),
          sheet_mappings: Object.fromEntries(
            Object.entries(tabMappings).map(([tab, data]) => [
              tab,
              {
                found: data.found,
                excel_sheet_name: data.excel_sheet_name,
                columns: data.columns,
                sample_row: data.sample_row,
                column_mappings: serializeGstr2bColumnMappings(data.column_mappings),
              },
            ]),
          ),
        }),
      });
    },
    onSuccess: () => navigate("/app/data-mapping/gstr-2b?saved=1"),
    onError: (err) => {
      setReviewError(err instanceof ApiError ? err.message : "Could not save mapping");
      setActiveStep(2);
    },
  });

  const sortedFields = useMemo(
    () =>
      [...masterFields].sort(
        (a, b) => a.display_order - b.display_order || a.field_name.localeCompare(b.field_name),
      ),
    [masterFields],
  );

  const foundTabs = useMemo(() => GSTR2B_TABS.filter((tab) => tabMappings[tab]?.found), [tabMappings]);

  const validateDetails = (): boolean => {
    if (!mappingName.trim()) {
      setDetailsError("Mapping name is required.");
      return false;
    }
    if (!version.trim()) {
      setDetailsError("Version is required.");
      return false;
    }
    setDetailsError(null);
    return true;
  };

  const validateUpload = (): boolean => {
    if (!isEdit && !uploadFile) {
      setUploadError("GSTR-2B Excel file is required when creating a new mapping.");
      return false;
    }
    if (isEdit && !uploadFile && foundTabs.length === 0) {
      setUploadError("Upload a GSTR-2B Excel file or keep existing sheet mappings.");
      return false;
    }
    setUploadError(null);
    return true;
  };

  const validateReview = (): boolean => {
    if (foundTabs.length === 0) {
      setReviewError("At least one supported GSTR-2B sheet must be found in the uploaded file.");
      return false;
    }

    const errors: string[] = [];
    for (const tab of foundTabs) {
      const data = tabMappings[tab];
      const dup = findDuplicateColumnMappingsForTab(data.column_mappings);
      if (dup) {
        errors.push(`${tab}: ${dup}`);
        continue;
      }
      for (const field of sortedFields) {
        if (isFieldRequiredForGstr2b(field.field_code, field.is_required, data.column_mappings)) {
          errors.push(`${tab}: ${field.field_name} must be mapped or marked N/A`);
        }
      }
      if (CDNR_TABS.has(tab) && !isGstr2bMappingSet(data.column_mappings.note_type)) {
        errors.push(`${tab}: Note Type must be mapped or marked N/A`);
      }
    }

    if (errors.length > 0) {
      setReviewError(errors.join("; "));
      return false;
    }
    setReviewError(null);
    return true;
  };

  const handleResetAutoMapping = (tab: string) => {
    const data = tabMappings[tab];
    if (!data.found || data.columns.length === 0) return;
    const fieldCodes = sortedFields.map((f) => f.field_code);
    const { mappings, confidence } = autoMatchGstr2bColumns(
      fieldCodes,
      data.columns,
      CDNR_TABS.has(tab as (typeof GSTR2B_TABS)[number]),
      tab,
    );
    setTabMappings((prev) => ({
      ...prev,
      [tab]: { ...prev[tab], column_mappings: mappings, auto_match_confidence: confidence },
    }));
    setReviewError(null);
  };

  const handleMappingChange = (tab: string, fieldCode: string, column: string) => {
    const value = column || null;
    setTabMappings((prev) => ({
      ...prev,
      [tab]: {
        ...prev[tab],
        column_mappings: { ...prev[tab].column_mappings, [fieldCode]: value },
        auto_match_confidence: {
          ...prev[tab].auto_match_confidence,
          [fieldCode]: isGstr2bNaMapping(value) ? "none" : prev[tab].auto_match_confidence[fieldCode] ?? "none",
        },
      },
    }));
    setReviewError(null);
  };

  const mappingSampleValue = (selectedCol: string, sampleRow: Record<string, string>) => {
    if (!selectedCol) return "—";
    if (isGstr2bNaMapping(selectedCol)) return GSTR2B_NA_LABEL;
    return sampleRow[selectedCol] || "—";
  };

  const goNext = () => {
    if (activeStep === 0) {
      if (!validateDetails()) return;
      setActiveStep(1);
      return;
    }
    if (activeStep === 1) {
      if (!validateUpload()) return;
      if (uploadFile) {
        parseMutation.mutate(uploadFile);
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
      setUploadError("GSTR-2B Excel file is required.");
      setActiveStep(1);
      return;
    }
    setReviewError(null);
    saveMutation.mutate();
  };

  const currentTabData = tabMappings[reviewTab] ?? emptyTabMapping(reviewTab);

  if (isEdit && detailQ.isLoading) {
    return (
      <Box py={4}>
        <Typography color="text.secondary">Loading mapping…</Typography>
      </Box>
    );
  }

  if (isEdit && detailQ.isError) {
    return <Alert severity="error">{detailQ.error instanceof ApiError ? detailQ.error.message : "Failed to load mapping"}</Alert>;
  }

  return (
    <Box>
      <Typography variant="h5" fontWeight={600} mb={1}>
        {isEdit ? "Edit GSTR-2B Mapping" : "Create GSTR-2B Mapping"}
      </Typography>
      <Typography color="text.secondary" mb={3}>
        Map GST portal GSTR-2B Excel columns to reconciliation master fields by sheet tab.
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
              <TextField
                label="Version Name or Number"
                value={version}
                onChange={(e) => {
                  setVersion(e.target.value);
                  setDetailsError(null);
                }}
                required
                fullWidth
                helperText="e.g. v1, 2026-Q1, Portal format Jan 2026"
              />
              {isEdit && (
                <Alert severity={isActive ? "success" : "info"}>
                  This version is currently <strong>{isActive ? "Active" : "Inactive"}</strong>.
                  {!isActive && " Use Mark as Active on the list screen to activate it."}
                </Alert>
              )}
              {!isEdit && (
                <Alert severity="info">New mapping versions are marked active automatically when saved.</Alert>
              )}
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
                  Current file: <strong>{existingFilename}</strong>. Upload a new file to remap all supported sheets.
                </Alert>
              )}
              <Button variant="outlined" component="label" startIcon={<UploadFileOutlined />}>
                Choose GSTR-2B Excel File
                <input
                  hidden
                  type="file"
                  accept=".xls,.xlsx,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (!file) return;
                    if (!isAcceptedExcel(file)) {
                      setUploadError("Please upload a .xls or .xlsx file.");
                      return;
                    }
                    setUploadFile(file);
                    setExistingFilename(file.name);
                    setUploadError(null);
                  }}
                />
              </Button>
              {uploadFile && (
                <Typography variant="body2" color="text.secondary">
                  Selected: {uploadFile.name}
                </Typography>
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
              Some columns were not confidently matched across sheets. Review highlighted fields before saving.
            </Alert>
          )}

          <Tabs
            value={reviewTab}
            onChange={(_, v) => setReviewTab(v)}
            variant="scrollable"
            scrollButtons="auto"
          >
            {GSTR2B_TABS.map((tab) => {
              const data = tabMappings[tab];
              const status = tabStatus(data, sortedFields);
              return (
                <Tab
                  key={tab}
                  value={tab}
                  label={
                    <Stack direction="row" spacing={0.5} alignItems="center">
                      <span>{tab}</span>
                      {data.found ? (
                        status === "complete" ? (
                          <Chip size="small" label="Complete" color="success" variant="outlined" />
                        ) : (
                          <Chip size="small" label="Incomplete" color="warning" variant="outlined" />
                        )
                      ) : (
                        <Chip size="small" label="Not found" variant="outlined" />
                      )}
                    </Stack>
                  }
                />
              );
            })}
          </Tabs>

          {!currentTabData.found ? (
            <Alert severity="info">This sheet was not found in the uploaded file.</Alert>
          ) : (
            <>
              <Stack direction="row" justifyContent="space-between" alignItems="center">
                <Typography variant="body2" color="text.secondary">
                  Matched Excel sheet: <strong>{currentTabData.excel_sheet_name}</strong>
                </Typography>
                <Button size="small" onClick={() => handleResetAutoMapping(reviewTab)}>
                  Reset Auto Mapping
                </Button>
              </Stack>

              {CDNR_TABS.has(reviewTab as (typeof GSTR2B_TABS)[number]) && (
                <Alert severity="info">{NOTE_TYPE_FIELD.helperText}</Alert>
              )}

              <Card variant="outlined">
                <CardContent sx={{ p: 0, "&:last-child": { pb: 0 } }}>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>Master Field</TableCell>
                        <TableCell>GSTR-2B Excel Column</TableCell>
                        <TableCell>Sample Value</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {sortedFields.map((field) => {
                        const selectedCol = currentTabData.column_mappings[field.field_code] ?? "";
                        const isNa = isGstr2bNaMapping(selectedCol);
                        const conf =
                          currentTabData.auto_match_confidence[field.field_code] ??
                          (selectedCol && !isNa ? "high" : "none");
                        const required = isFieldRequiredForGstr2b(
                          field.field_code,
                          field.is_required,
                          currentTabData.column_mappings,
                        );
                        const lowConf = !isNa && (conf === "low" || (!selectedCol && conf === "none"));
                        return (
                          <TableRow
                            key={field.field_code}
                            sx={{
                              bgcolor: required && !selectedCol
                                ? "rgba(211, 47, 47, 0.06)"
                                : lowConf
                                  ? "rgba(237, 108, 2, 0.06)"
                                  : undefined,
                            }}
                          >
                            <TableCell>
                              <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
                                <Typography variant="body2">
                                  {field.field_name}
                                  {required ? " *" : ""}
                                </Typography>
                                {isNa && (
                                  <Chip size="small" label="Not available" variant="outlined" />
                                )}
                                {conf === "high" && selectedCol && !isNa && (
                                  <Chip size="small" label="Auto-matched" color="success" variant="outlined" />
                                )}
                                {conf === "low" && (
                                  <Chip size="small" label="Low confidence" color="warning" variant="outlined" />
                                )}
                                {field.field_code === "company_gstin" && (
                                  <Chip size="small" label="Optional" variant="outlined" />
                                )}
                                {field.field_code === "total_tax" && !selectedCol && (
                                  <Chip size="small" label="Can derive" variant="outlined" />
                                )}
                              </Stack>
                            </TableCell>
                            <TableCell sx={{ minWidth: 220 }}>
                              <FormControl fullWidth size="small" error={required && !selectedCol}>
                                <Select
                                  value={selectedCol}
                                  displayEmpty
                                  onChange={(e) => handleMappingChange(reviewTab, field.field_code, e.target.value)}
                                >
                                  <MenuItem value="">
                                    <em>Select column</em>
                                  </MenuItem>
                                  <MenuItem value={GSTR2B_NA_VALUE}>{GSTR2B_NA_LABEL}</MenuItem>
                                  {currentTabData.columns.map((col) => (
                                    <MenuItem key={col} value={col}>
                                      {col}
                                    </MenuItem>
                                  ))}
                                </Select>
                              </FormControl>
                            </TableCell>
                            <TableCell>
                              <Typography variant="body2" color="text.secondary" sx={{ fontFamily: "monospace" }}>
                                {mappingSampleValue(selectedCol, currentTabData.sample_row)}
                              </Typography>
                            </TableCell>
                          </TableRow>
                        );
                      })}
                      {CDNR_TABS.has(reviewTab as (typeof GSTR2B_TABS)[number]) && (() => {
                        const noteTypeCol = currentTabData.column_mappings.note_type ?? "";
                        const noteTypeNa = isGstr2bNaMapping(noteTypeCol);
                        const noteTypeRequired = !isGstr2bMappingSet(noteTypeCol);
                        return (
                          <TableRow
                            sx={{
                              bgcolor: noteTypeRequired ? "rgba(211, 47, 47, 0.06)" : undefined,
                            }}
                          >
                            <TableCell>
                              <Stack direction="row" spacing={1} alignItems="center">
                                <Typography variant="body2">{NOTE_TYPE_FIELD.name} *</Typography>
                                {noteTypeNa && (
                                  <Chip size="small" label="Not available" variant="outlined" />
                                )}
                                {currentTabData.auto_match_confidence.note_type === "high" &&
                                  noteTypeCol &&
                                  !noteTypeNa && (
                                    <Chip size="small" label="Auto-matched" color="success" variant="outlined" />
                                  )}
                              </Stack>
                            </TableCell>
                            <TableCell sx={{ minWidth: 220 }}>
                              <FormControl fullWidth size="small" error={noteTypeRequired}>
                                <Select
                                  value={noteTypeCol}
                                  displayEmpty
                                  onChange={(e) => handleMappingChange(reviewTab, "note_type", e.target.value)}
                                >
                                  <MenuItem value="">
                                    <em>Select column</em>
                                  </MenuItem>
                                  <MenuItem value={GSTR2B_NA_VALUE}>{GSTR2B_NA_LABEL}</MenuItem>
                                  {currentTabData.columns.map((col) => (
                                    <MenuItem key={col} value={col}>
                                      {col}
                                    </MenuItem>
                                  ))}
                                </Select>
                              </FormControl>
                            </TableCell>
                            <TableCell>
                              <Typography variant="body2" color="text.secondary" sx={{ fontFamily: "monospace" }}>
                                {mappingSampleValue(noteTypeCol, currentTabData.sample_row)}
                              </Typography>
                            </TableCell>
                          </TableRow>
                        );
                      })()}
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>
            </>
          )}
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
                <strong>Version:</strong> {version}
              </Typography>
              <Typography>
                <strong>File:</strong> {uploadFile?.name ?? existingFilename ?? "—"}
              </Typography>
              <Typography>
                <strong>Sheets found:</strong> {foundTabs.length} of {GSTR2B_TABS.length}
              </Typography>
              {!isEdit && (
                <Typography color="text.secondary">
                  This version will be marked as the active GSTR-2B mapping when saved.
                </Typography>
              )}
              {saveMutation.isError && (
                <Alert severity="error">
                  {saveMutation.error instanceof ApiError ? saveMutation.error.message : "Could not save mapping"}
                </Alert>
              )}
            </Stack>
          </CardContent>
        </Card>
      )}

      <Stack direction="row" justifyContent="space-between" mt={3}>
        <Button onClick={() => navigate("/app/data-mapping/gstr-2b")}>Cancel</Button>
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
