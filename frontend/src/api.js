const trimSlashes = (value) =>
  String(value ?? "")
    .trim()
    .replace(/^\/+|\/+$/g, "");

export const apiConfig = {
  baseUrl: (
    import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:5000"
  ).replace(/\/+$/, ""),
  healthPath: import.meta.env.VITE_API_HEALTH_PATH || "/",
  historyPath: trimSlashes(import.meta.env.VITE_API_EMAILS_PATH),
  sendPath: trimSlashes(import.meta.env.VITE_API_SEND_PATH),
  schedulePath: trimSlashes(import.meta.env.VITE_API_SCHEDULE_PATH),
};

export class ApiRequestError extends Error {
  constructor(message, status, body) {
    super(message);
    this.name = "ApiRequestError";
    this.status = status;
    this.body = body;
  }
}

function endpointUrl(config, path) {
  if (!path) throw new Error("This API route has not been configured.");
  return `${config.baseUrl}/${String(path).replace(/^\/+/, "")}`;
}

async function parseBody(response) {
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

async function request(config, path, init, allowNonOk = false) {
  const response = await fetch(endpointUrl(config, path), init);
  const body = await parseBody(response);
  if (!response.ok && !allowNonOk) {
    const message =
      typeof body === "object" && body
        ? body.message ||
          body.error ||
          `Request failed with HTTP ${response.status}.`
        : `Request failed with HTTP ${response.status}.`;
    throw new ApiRequestError(String(message), response.status, body);
  }
  return { response, body };
}

export async function checkHealth(config = apiConfig) {
  const { body } = await request(config, config.healthPath, {
    method: "GET",
    cache: "no-store",
  });
  return body;
}

export async function fetchEmailRecords(config = apiConfig) {
  const { body } = await request(config, config.historyPath, {
    method: "GET",
    cache: "no-store",
  });
  const emails = Array.isArray(body) ? body : body?.emails;
  if (!Array.isArray(emails)) {
    throw new Error(
      "The email history response did not include an emails array.",
    );
  }
  return emails.filter((record) => record && typeof record === "object");
}

function normalizeOutcome(body) {
  if (!body || typeof body !== "object") return "";
  const value =
    body.delivery_status ?? body.outcome ?? body.result ?? body.status;
  return typeof value === "string"
    ? value
        .trim()
        .toLowerCase()
        .replace(/[\s-]+/g, "_")
    : "";
}

function countFrom(body, names) {
  if (!body || typeof body !== "object") return undefined;
  for (const name of names) {
    const value = body[name];
    if (Number.isFinite(value)) return value;
  }
  return undefined;
}

export function classifySendResponse(statusCode, body) {
  const outcome = normalizeOutcome(body);
  const sentCount = countFrom(body, [
    "sent_count",
    "emails_sent",
    "success_count",
    "succeeded",
  ]);
  const failedCount = countFrom(body, [
    "failed_count",
    "emails_failed",
    "failure_count",
    "failed",
  ]);
  const explicitNoDelivery =
    body?.no_emails_sent === true ||
    body?.emails_sent === 0 ||
    body?.sent_count === 0;
  const isDuplicate = [
    "duplicate",
    "already_processed",
    "idempotency_duplicate",
  ].includes(outcome);
  const isPartial =
    ["partial", "partial_success", "partially_failed", "mixed"].includes(
      outcome,
    ) ||
    (Number.isFinite(sentCount) &&
      sentCount > 0 &&
      Number.isFinite(failedCount) &&
      failedCount > 0);
  const isFailure = ["failed", "failure", "error", "rejected"].includes(
    outcome,
  );
  const isSuccess =
    ["success", "sent", "delivered", "accepted", "queued"].includes(outcome) ||
    body?.success === true;

  if (isDuplicate) return "duplicate";
  if (isPartial) return "partial";
  if (statusCode >= 500 && !(isFailure && explicitNoDelivery))
    return "uncertain";
  if (isFailure) return "failed";
  if (isSuccess && statusCode >= 200 && statusCode < 300) return "success";
  if (statusCode < 200 || statusCode >= 300)
    return statusCode >= 500 ? "uncertain" : "failed";
  return "uncertain";
}

export async function sendEmail(config, payload, idempotencyKey) {
  const { response, body } = await request(
    config,
    config.sendPath,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": idempotencyKey,
      },
      body: JSON.stringify(payload),
    },
    true,
  );

  return {
    statusCode: response.status,
    body,
    outcome: classifySendResponse(response.status, body),
  };
}

export async function scheduleEmail(config, payload, idempotencyKey) {
  const { response, body } = await request(
    config,
    config.schedulePath,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": idempotencyKey,
      },
      body: JSON.stringify(payload),
    },
    true,
  );
  const apiOutcome = normalizeOutcome(body);
  const responseText = typeof body === "string" ? body.trim() : "";
  const explicitlyFailed =
    ["failed", "failure", "error", "rejected"].includes(apiOutcome) ||
    /^(failed|failure|error|rejected)\b/i.test(responseText) ||
    body?.success === false;

  return {
    statusCode: response.status,
    body,
    outcome: response.ok && !explicitlyFailed ? "scheduled" : "failed",
  };
}

export const SCHEDULE_TIME_ZONE = "Africa/Cairo";

const cairoDateTimeFormatter = new Intl.DateTimeFormat("en-GB", {
  timeZone: SCHEDULE_TIME_ZONE,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});

function cairoParts(timestamp) {
  return Object.fromEntries(
    cairoDateTimeFormatter
      .formatToParts(new Date(timestamp))
      .filter((part) => part.type !== "literal")
      .map((part) => [part.type, Number(part.value)]),
  );
}

export function cairoWallTimeToDate(dateValue, timeValue) {
  const dateMatch = /^(\d{4})-(\d{2})-(\d{2})$/.exec(dateValue || "");
  const timeMatch = /^(\d{2}):(\d{2})$/.exec(timeValue || "");
  if (!dateMatch || !timeMatch) return null;

  const [, year, month, day] = dateMatch.map(Number);
  const [, hour, minute] = timeMatch.map(Number);
  if (
    month < 1 ||
    month > 12 ||
    day < 1 ||
    day > 31 ||
    hour > 23 ||
    minute > 59
  )
    return null;

  const requestedUtc = Date.UTC(year, month - 1, day, hour, minute);
  let candidate = requestedUtc;
  for (let attempt = 0; attempt < 4; attempt += 1) {
    const parts = cairoParts(candidate);
    const representedUtc = Date.UTC(
      parts.year,
      parts.month - 1,
      parts.day,
      parts.hour,
      parts.minute,
    );
    const next = requestedUtc - (representedUtc - candidate);
    if (next === candidate) break;
    candidate = next;
  }

  const resolved = cairoParts(candidate);
  const isExact =
    resolved.year === year &&
    resolved.month === month &&
    resolved.day === day &&
    resolved.hour === hour &&
    resolved.minute === minute;
  return isExact ? new Date(candidate) : null;
}

export function currentCairoDate() {
  const parts = cairoParts(Date.now());
  return `${parts.year}-${String(parts.month).padStart(2, "0")}-${String(parts.day).padStart(2, "0")}`;
}

export function formatCairoDateTime(value) {
  if (!value || Number.isNaN(new Date(value).getTime()))
    return "Date unavailable";
  return `${new Intl.DateTimeFormat(undefined, {
    timeZone: SCHEDULE_TIME_ZONE,
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZoneName: "short",
  }).format(new Date(value))} (${SCHEDULE_TIME_ZONE})`;
}

export function responseMessage(body) {
  if (typeof body === "string") return body;
  if (!body || typeof body !== "object") return "";
  const message = body.message ?? body.error_description ?? body.error;
  return typeof message === "string" ? message : "";
}

const firstValue = (record, keys) => {
  for (const key of keys) {
    const value = record?.[key];
    if (value !== undefined && value !== null && value !== "") return value;
  }
  return undefined;
};

export function recordRecipients(record) {
  const raw = firstValue(record, [
    "recipient_emails",
    "recipients",
    "recipient_email",
    "recipient",
    "to",
    "email",
  ]);
  if (Array.isArray(raw)) return raw.map(String).filter(Boolean);
  if (typeof raw === "string")
    return raw
      .split(/[;,\n]/)
      .map((item) => item.trim())
      .filter(Boolean);
  return [];
}

export function recordSubject(record) {
  const value = firstValue(record, ["subject", "email_subject"]);
  return typeof value === "string" ? value : "";
}

export function recordPreview(record) {
  const value = firstValue(record, [
    "body",
    "message",
    "content",
    "email_body",
  ]);
  return typeof value === "string" ? value.replace(/\s+/g, " ").trim() : "";
}

export function recordDateValue(record) {
  return firstValue(record, [
    "created_at",
    "sent_at",
    "timestamp",
    "date",
    "created",
    "sent",
  ]);
}

export function recordScheduledDateValue(record) {
  return firstValue(record, [
    "scheduled_at",
    "scheduled_for",
    "scheduled_send_at",
    "scheduled_datetime",
  ]);
}

export function recordStatusValue(record) {
  const value = firstValue(record, [
    "delivery_status",
    "status",
    "result",
    "outcome",
  ]);
  return typeof value === "string"
    ? value
        .trim()
        .toLowerCase()
        .replace(/[\s-]+/g, "_")
    : "";
}

export function recordStatus(record) {
  const value = recordStatusValue(record);
  if (
    [
      "success",
      "sent",
      "delivered",
      "accepted",
      "complete",
      "completed",
    ].includes(value)
  )
    return "success";
  if (
    ["partial", "partial_success", "partially_failed", "mixed"].includes(value)
  )
    return "partial";
  if (["failed", "failure", "error", "rejected", "bounced"].includes(value))
    return "failed";
  if (
    ["duplicate", "already_processed", "idempotency_duplicate"].includes(value)
  )
    return "duplicate";
  if (
    [
      "scheduled",
      "scheduled_successfully",
      "scheduled_job",
      "queued",
      "pending",
      "processing",
    ].includes(value)
  )
    return "scheduled";
  if (["uncertain", "unknown"].includes(value)) return "uncertain";
  return "recorded";
}

export function formatRecordDate(value) {
  if (!value) return "Date unavailable";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

export function getEmailMetrics(records) {
  const successful = records.filter(
    (record) => recordStatus(record) === "success",
  ).length;
  const failed = records.filter(
    (record) => recordStatus(record) === "failed",
  ).length;
  const recipients = new Set(
    records.flatMap(recordRecipients).map((email) => email.toLowerCase()),
  );
  return {
    total: records.length,
    successful,
    failed,
    uniqueRecipients: recipients.size,
  };
}
