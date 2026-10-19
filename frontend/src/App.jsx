import { useMemo, useRef, useState } from "react";
import useSWR from "swr";
import {
  Activity, AlertCircle, ArrowDownRight, ArrowUpRight, Check, CheckCircle2,
  ChevronDown, CircleHelp, Clock3, Inbox, LoaderCircle, Mail, Menu,
  Plus, RefreshCw, Search, Send, ShieldCheck, Users, XCircle,
} from "lucide-react";
import {
  apiConfig, cairoWallTimeToDate, checkHealth, classifySendResponse, currentCairoDate,
  fetchEmailRecords, formatCairoDateTime, formatRecordDate, getEmailMetrics,
  recordDateValue, recordRecipients, recordStatus,
  responseMessage, SCHEDULE_TIME_ZONE, scheduleEmail, sendEmail,
} from "./api";
import { EmailTable, RecentActivity } from "./components/EmailTable";
import { Sidebar } from "./components/Sidebar";

const pageTitles = { overview: "Overview", compose: "Compose email", history: "Email history" };
const validEmail = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function getRecipients(value) {
  return value.split(/[;,\n]/).map((email) => email.trim()).filter(Boolean);
}

function getStatusLabel(result) {
  if (result.type === "scheduled") return result.outcome === "scheduled" ? "Scheduled successfully" : "Scheduling failed";
  if (result.type === "immediate" && result.outcome === "success") return "Sent immediately";
  return {
    success: "API reported success",
    partial: "Partial delivery result",
    failed: "Request failed",
    duplicate: "Duplicate request",
    uncertain: "Delivery is uncertain",
  }[result.outcome] || "Delivery status unavailable";
}

function ApiStatus({ health, healthError, hasAnyRoute }) {
  if (!hasAnyRoute) return <span className="api-pill api-pill-muted"><span className="api-pill-dot" />Routes need setup</span>;
  if (healthError) return <span className="api-pill api-pill-error"><span className="api-pill-dot" />API unavailable</span>;
  if (health?.status === "success") return <span className="api-pill api-pill-connected"><span className="api-pill-dot" />API connected</span>;
  if (health) return <span className="api-pill api-pill-muted"><span className="api-pill-dot" />API status unknown</span>;
  return <span className="api-pill api-pill-muted"><span className="api-pill-dot" />Checking API</span>;
}

function PageHeader({ view, onMenu, health, healthError, hasAnyRoute, onRefresh, refreshing, onCompose }) {
  return (
    <header className="topbar">
      <div className="topbar-leading">
        <button className="icon-button mobile-menu-button" type="button" onClick={onMenu} aria-label="Open navigation menu"><Menu size={20} /></button>
        <div className="breadcrumbs"><span>MailFlow</span><span className="breadcrumb-divider">/</span><h1>{pageTitles[view]}</h1></div>
      </div>
      <div className="topbar-actions">
        <ApiStatus health={health} healthError={healthError} hasAnyRoute={hasAnyRoute} />
        <button className="icon-button refresh-button" type="button" onClick={onRefresh} disabled={refreshing} aria-label="Refresh email data" title="Refresh email data">
          <RefreshCw size={17} className={refreshing ? "spin" : ""} />
        </button>
        <span className="topbar-divider" aria-hidden="true" />
        <button className="topbar-cta" type="button" onClick={onCompose}><Plus size={16} /> <span>New email</span></button>
      </div>
    </header>
  );
}

function SetupNotice({ missingRoutes, compact = false }) {
  if (missingRoutes.length === 0) return null;
  return (
    <div className={`setup-notice${compact ? " setup-notice-compact" : ""}`} role="status">
      <span className="setup-notice-icon"><CircleHelp size={18} /></span>
      <div>
        <strong>Connect your existing Flask API</strong>
        <p>Set {missingRoutes.map((route) => <code key={route}>{route}</code>)} in your Vite environment to enable the matching feature. No route names are assumed.</p>
      </div>
    </div>
  );
}

function SummaryCard({ icon: Icon, label, value, footnote, tone = "blue" }) {
  return (
    <article className="summary-card">
      <div className={`summary-icon summary-icon-${tone}`}><Icon size={18} strokeWidth={1.8} aria-hidden="true" /></div>
      <div className="summary-label">{label}</div>
      <div className="summary-value">{value}</div>
      <div className="summary-footnote">{footnote}</div>
    </article>
  );
}

function Overview({ records, historyConfigured, historyLoading, historyError, missingRoutes, onCompose, onHistory }) {
  const metrics = getEmailMetrics(records);
  const display = (value) => historyConfigured && !historyError && !historyLoading ? value.toLocaleString() : "—";
  const datesAvailable = records.some((record) => recordDateValue(record));
  const successfulRecent = records.filter((record) => recordStatus(record) === "success").length;
  const completedActivity = historyConfigured && !historyLoading && !historyError;

  return (
    <div className="page-content overview-page">
      <section className="welcome-banner">
        <div className="welcome-copy">
          <div className="welcome-kicker"><span className="welcome-spark" /> YOUR EMAIL WORKSPACE</div>
          <h2>Good email starts<br className="desktop-break" /> with a clear view.</h2>
          <p>Send through your existing SMTP-powered API and keep every recorded email in one place.</p>
          <button className="welcome-button" type="button" onClick={onCompose}><Mail size={16} /> Compose an email <ArrowUpRight size={15} /></button>
        </div>
        <div className="welcome-art" aria-hidden="true">
          <span className="art-ring art-ring-one" /><span className="art-ring art-ring-two" />
          <span className="art-spark art-spark-one">✳</span><span className="art-spark art-spark-two">✦</span>
          <span className="art-envelope"><Mail size={42} strokeWidth={1.25} /></span>
          <span className="art-check"><Check size={16} strokeWidth={2.7} /></span>
        </div>
        <div className="banner-orb banner-orb-one" aria-hidden="true" /><div className="banner-orb banner-orb-two" aria-hidden="true" />
      </section>

      <SetupNotice missingRoutes={missingRoutes} />

      {historyError && <div className="inline-alert inline-alert-error" role="alert"><AlertCircle size={17} /><span>Email history could not be loaded. {historyError.message}</span></div>}

      <section className="summary-grid" aria-label="Email activity summary">
        <SummaryCard icon={Inbox} label="Recorded emails" value={display(metrics.total)} footnote="Records returned by your API" tone="blue" />
        <SummaryCard icon={CheckCircle2} label="API-reported sent" value={display(metrics.successful)} footnote="Successful records only" tone="green" />
        <SummaryCard icon={XCircle} label="Recorded failures" value={display(metrics.failed)} footnote="Explicit failure statuses" tone="rose" />
        <SummaryCard icon={Users} label="Unique recipients" value={display(metrics.uniqueRecipients)} footnote="From returned email records" tone="violet" />
      </section>

      <div className="overview-grid">
        <RecentActivity records={records} onViewAll={onHistory} />
        <aside className="overview-aside">
          <section className="panel health-panel">
            <div className="panel-heading panel-heading-small"><div><p className="eyebrow">DELIVERY CONNECTION</p><h2>Backend status</h2></div><span className="health-icon"><Activity size={17} /></span></div>
            <div className="health-state-row"><span className={`health-indicator${historyError ? " health-indicator-error" : ""}`} /><strong>{historyError ? "Check your API connection" : "Existing Flask API"}</strong></div>
            <p className="health-description">MailFlow only displays records and outcomes returned by your configured API. No delivery metrics are simulated.</p>
            <div className="connection-details"><span>Base URL</span><code>{apiConfig.baseUrl}</code></div>
            <div className="connection-details"><span>Email records</span><strong>{completedActivity ? `${records.length} returned` : historyLoading ? "Loading…" : "Not connected"}</strong></div>
          </section>
          <section className="insight-panel">
            <div className="insight-icon"><ShieldCheck size={19} /></div>
            <p className="eyebrow">BUILT FOR CONFIDENCE</p>
            <h3>Know what happened before you try again.</h3>
            <p>Unconfirmed sends are flagged clearly. MailFlow never automatically resends a request.</p>
            <div className="insight-stat"><span>{completedActivity ? successfulRecent.toLocaleString() : "—"}</span><span>successful records in returned history</span></div>
            <button className="text-button insight-link" type="button" onClick={onCompose}>Write an email <ArrowUpRight size={15} /></button>
          </section>
        </aside>
      </div>
      {completedActivity && records.length > 0 && !datesAvailable && <p className="data-footnote"><Clock3 size={13} /> Date fields are not present in the returned records; dates are shown as unavailable in history.</p>}
    </div>
  );
}

function OutcomeNotice({ result }) {
  if (!result) return null;
  const isGood = result.type === "scheduled" ? result.outcome === "scheduled" : result.outcome === "success";
  const Icon = isGood ? CheckCircle2 : result.outcome === "failed" ? XCircle : AlertCircle;
  let description = result.message;
  if (result.type === "scheduled" && result.outcome === "scheduled") description ||= "The Flask API confirmed this scheduled job.";
  else if (result.type === "scheduled") description ||= "The scheduled job was not confirmed by the Flask API. Check the API response or email history before retrying.";
  else if (result.outcome === "success") description ||= "The API reported a successful immediate send.";
  if (result.outcome === "partial") description ||= "The API reported a partial result. Review the backend response and history before sending again.";
  if (result.outcome === "failed") description ||= "The API reported that this request failed. Review the response before trying again.";
  if (result.outcome === "duplicate") description ||= "The API recognized this idempotency key as a duplicate. Check email history for the recorded outcome; do not create a new request blindly.";
  if (result.outcome === "uncertain") description ||= "We could not confirm the delivery outcome. Do not retry blindly—check email history or your SMTP logs first.";
  return (
    <div className={`outcome-notice outcome-${result.type === "scheduled" ? (isGood ? "success" : "failed") : result.outcome}`} role={isGood ? "status" : "alert"} aria-live={isGood ? "polite" : "assertive"}>
      <Icon size={20} className="outcome-icon" aria-hidden="true" />
      <div className="outcome-copy"><strong>{getStatusLabel(result)}</strong><p>{description}</p><span>HTTP {result.statusCode}</span></div>
    </div>
  );
}

function Field({ label, hint, children, className = "" }) {
  return <div className={`form-field ${className}`}><div className="field-heading"><label htmlFor={children.props.id}>{label}</label>{hint && <span>{hint}</span>}</div>{children}</div>;
}

function ComposePage({ sendConfigured, scheduleConfigured, onSubmit, isSending, result, formError, mode, setMode, recipient, setRecipient, subject, setSubject, body, setBody, deliveryMode, setDeliveryMode, scheduleDate, setScheduleDate, scheduleTime, setScheduleTime }) {
  const recipients = mode === "single" ? [recipient.trim()].filter(Boolean) : getRecipients(recipient);
  const recipientHint = mode === "multiple" ? `${recipients.length} recipient${recipients.length === 1 ? "" : "s"}` : "Only you can see this field";
  const scheduledAt = cairoWallTimeToDate(scheduleDate, scheduleTime);
  const isScheduledTimeFuture = scheduledAt && scheduledAt.getTime() > Date.now();

  return (
    <div className="page-content compose-page">
      <div className="page-intro"><div><p className="eyebrow">A NOTE, WELL SENT</p><h2>Compose an email</h2><p>Write your message and choose when the Flask API should send it.</p></div><span className="compose-intro-icon"><Send size={21} /></span></div>
      <SetupNotice missingRoutes={deliveryMode === "scheduled" ? (scheduleConfigured ? [] : ["VITE_API_SCHEDULE_PATH"]) : (sendConfigured ? [] : ["VITE_API_SEND_PATH"])} compact />
      <div className="compose-layout">
        <section className="panel compose-panel">
          <div className="compose-panel-heading"><div className="compose-heading-icon"><Mail size={18} /></div><div><h3>New message</h3><p>Fields marked with an asterisk are required.</p></div></div>
          <form className="compose-form" onSubmit={onSubmit}>
            <div className="recipient-mode-row">
              <span className="field-static-label">Recipient mode</span>
              <div className="segmented-control" role="group" aria-label="Recipient mode">
                <button type="button" className={mode === "single" ? "segment-active" : ""} onClick={() => { setMode("single"); setRecipient(""); }}>Single recipient</button>
                <button type="button" className={mode === "multiple" ? "segment-active" : ""} onClick={() => { setMode("multiple"); setRecipient(""); }}>Multiple recipients</button>
              </div>
            </div>
            <div className="delivery-mode-field">
              <span className="field-static-label">Sending mode</span>
              <div className="delivery-mode-options" role="group" aria-label="Sending mode">
                <button type="button" className={`delivery-mode-option${deliveryMode === "immediate" ? " delivery-mode-active" : ""}`} onClick={() => setDeliveryMode("immediate")} aria-pressed={deliveryMode === "immediate"}>
                  <Send size={15} /><span><strong>Send Immediately</strong><small>Send as soon as you submit</small></span>
                </button>
                <button type="button" className={`delivery-mode-option${deliveryMode === "scheduled" ? " delivery-mode-active" : ""}`} onClick={() => setDeliveryMode("scheduled")} aria-pressed={deliveryMode === "scheduled"}>
                  <Clock3 size={15} /><span><strong>Schedule for Later</strong><small>Choose a Cairo date and time</small></span>
                </button>
              </div>
            </div>
            {deliveryMode === "scheduled" && <div className="schedule-fields">
              <Field label="Scheduled date *">
                <input id="schedule-date" className="form-input" type="date" min={currentCairoDate()} value={scheduleDate} onChange={(event) => setScheduleDate(event.target.value)} required />
              </Field>
              <Field label="Scheduled time *" hint={SCHEDULE_TIME_ZONE}>
                <input id="schedule-time" className="form-input" type="time" value={scheduleTime} onChange={(event) => setScheduleTime(event.target.value)} required />
              </Field>
              {scheduledAt && <div className={`schedule-preview${isScheduledTimeFuture ? "" : " schedule-preview-invalid"}`} role="status">
                <Clock3 size={15} /><span><strong>{isScheduledTimeFuture ? "Scheduled for" : "This time has passed"}</strong><span>{formatCairoDateTime(scheduledAt)}</span></span>
              </div>}
              {scheduleDate && scheduleTime && !scheduledAt && <p className="schedule-validation" role="alert">That local time is not valid in {SCHEDULE_TIME_ZONE}. Choose another time.</p>}
              {scheduledAt && !isScheduledTimeFuture && <p className="schedule-validation" role="alert">Choose a date and time in the future ({SCHEDULE_TIME_ZONE}).</p>}
            </div>}
            <Field label={mode === "single" ? "Recipient email *" : "Recipient emails *"} hint={recipientHint}>
              {mode === "single" ? (
                <input id="recipient" className="form-input" type="email" autoComplete="email" placeholder="name@company.com" value={recipient} onChange={(event) => setRecipient(event.target.value)} required />
              ) : (
                <textarea id="recipient" className="form-input recipient-textarea" placeholder={"alex@company.com\nsam@company.com"} value={recipient} onChange={(event) => setRecipient(event.target.value)} rows={3} required aria-describedby="recipient-help" />
              )}
            </Field>
            {mode === "multiple" && <p id="recipient-help" className="field-help">Separate addresses with a comma, semicolon, or new line. The API receives a recipient_emails array.</p>}
            <Field label="Subject *" hint={`${subject.length}/160`}>
              <input id="subject" className="form-input" type="text" placeholder="A clear, helpful subject" value={subject} onChange={(event) => setSubject(event.target.value)} maxLength={160} required />
            </Field>
            <Field label="Message *" hint={`${body.length.toLocaleString()} characters`} className="message-field">
              <textarea id="message" className="form-input message-textarea" placeholder="Write your message here…" value={body} onChange={(event) => setBody(event.target.value)} rows={9} required />
            </Field>
            {formError && <div className="inline-alert inline-alert-error form-error" role="alert"><AlertCircle size={16} /><span>{formError}</span></div>}
            <OutcomeNotice result={result} />
            <div className="compose-form-footer"><span><ShieldCheck size={15} /> {deliveryMode === "scheduled" ? "Scheduled by your Flask backend" : "Sent through your configured SMTP backend"}</span><button className="send-button" type="submit" disabled={!(deliveryMode === "scheduled" ? scheduleConfigured : sendConfigured) || isSending}>{isSending ? <LoaderCircle size={16} className="spin" /> : deliveryMode === "scheduled" ? <Clock3 size={16} /> : <Send size={16} />}<span>{isSending ? (deliveryMode === "scheduled" ? "Scheduling…" : "Sending…") : deliveryMode === "scheduled" ? "Schedule email" : "Send email"}</span></button></div>
            {deliveryMode === "scheduled" && !scheduleConfigured && <p className="disabled-note">Set VITE_API_SCHEDULE_PATH to your Flask scheduling route to enable scheduling.</p>}
            {deliveryMode === "immediate" && !sendConfigured && <p className="disabled-note">Set VITE_API_SEND_PATH to your existing Flask send route to enable sending.</p>}
          </form>
        </section>

        <aside className="compose-aside">
          <section className="panel send-summary-panel">
            <p className="eyebrow">MESSAGE SUMMARY</p><h3>Ready when you are.</h3>
            <div className="summary-line"><span>Recipient{recipients.length === 1 ? "" : "s"}</span><strong>{recipients.length || "—"}</strong></div>
            <div className="summary-line"><span>Subject</span><strong className={subject ? "summary-subject" : "muted-value"}>{subject || "Not added yet"}</strong></div>
            <div className="summary-line"><span>Message</span><strong>{body.length.toLocaleString()} characters</strong></div>
            <div className="summary-line"><span>Sending</span><strong>{deliveryMode === "scheduled" ? "Schedule for later" : "Immediately"}</strong></div>
            {deliveryMode === "scheduled" && <div className="summary-line summary-schedule-line"><span>Scheduled time</span><strong>{scheduledAt ? formatCairoDateTime(scheduledAt) : "Choose date and time"}</strong></div>}
            <div className="message-recipients-preview">{recipients.length > 0 ? recipients.slice(0, 4).map((email) => <span key={email}>{email}</span>) : <span>Recipient preview appears here</span>}{recipients.length > 4 && <span>+{recipients.length - 4} more</span>}</div>
          </section>
          <section className="safety-card"><div className="safety-card-icon"><ShieldCheck size={19} /></div><div><strong>Delivery safety</strong><p>Each logical submission reuses its idempotency key. MailFlow does not automatically retry, including after a server error.</p></div></section>
          <div className="send-flow"><span className="send-flow-icon">{deliveryMode === "scheduled" ? <Clock3 size={15} /> : <Mail size={15} />}</span><div><strong>Your message</strong><span>{deliveryMode === "scheduled" ? "Submitted as a scheduled job" : "Sent to your existing API"}</span></div><ArrowDownRight size={16} className="send-flow-arrow" /><span className="send-flow-icon send-flow-icon-last"><Activity size={15} /></span><div><strong>{deliveryMode === "scheduled" ? "Scheduled status" : "Recorded outcome"}</strong><span>Shown when the API responds</span></div></div>
        </aside>
      </div>
    </div>
  );
}

const historyFilters = [
  { id: "all", label: "All emails" },
  { id: "scheduled", label: "Scheduled" },
  { id: "success", label: "Sent" },
  { id: "partial", label: "Partial" },
  { id: "failed", label: "Failed" },
  { id: "uncertain", label: "Uncertain" },
];

function HistoryPage({ records, isLoading, error, historyConfigured, onRefresh, onCompose }) {
  const [filter, setFilter] = useState("all");
  const [query, setQuery] = useState("");
  const filtered = useMemo(() => records.filter((record) => {
    const matchesStatus = filter === "all" || recordStatus(record) === filter;
    const searchable = [record.subject, record.email_subject, record.body, record.message, ...recordRecipients(record)].filter(Boolean).join(" ").toLowerCase();
    return matchesStatus && searchable.includes(query.trim().toLowerCase());
  }), [records, filter, query]);

  return (
    <div className="page-content history-page">
      <div className="page-intro history-intro"><div><p className="eyebrow">EVERYTHING YOUR API HAS RECORDED</p><h2>Email history</h2><p>Review real email records returned by your Flask API.</p></div><button className="secondary-action" type="button" onClick={onRefresh}><RefreshCw size={15} /> Refresh</button></div>
      {!historyConfigured && <SetupNotice missingRoutes={["VITE_API_EMAILS_PATH"]} compact />}
      {error && <div className="inline-alert inline-alert-error" role="alert"><AlertCircle size={17} /><span>History could not be loaded. {error.message}</span></div>}
      <section className="panel history-panel">
        <div className="history-toolbar"><div className="history-filter-list" role="group" aria-label="Filter email history">
          {historyFilters.map((item) => <button className={`filter-button${filter === item.id ? " filter-active" : ""}`} type="button" key={item.id} onClick={() => setFilter(item.id)} aria-pressed={filter === item.id}>{item.label}{item.id === "all" && historyConfigured && <span>{records.length}</span>}</button>)}
        </div><label className="history-search"><Search size={16} aria-hidden="true" /><span className="sr-only">Search email history</span><input type="search" placeholder="Search history" value={query} onChange={(event) => setQuery(event.target.value)} /></label></div>
        {isLoading ? <div className="history-loading" role="status"><LoaderCircle size={18} className="spin" />Loading email records…</div>
          : filtered.length > 0 ? <EmailTable records={filtered} />
            : <EmailTable records={[]} emptyTitle={records.length === 0 ? "No recorded emails" : "No matching emails"} emptyDescription={records.length === 0 ? "When your API returns email records, they will appear here. Nothing is generated for this page." : "Try another search or status filter."} />}
      </section>
      <p className="history-footnote"><ShieldCheck size={14} /> Scheduled times and live statuses appear here when returned by your Flask API.</p>
      <button className="history-compose-link" type="button" onClick={onCompose}><Plus size={16} /> Compose an email</button>
    </div>
  );
}

function makeIdempotencyKey() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  return `mailflow-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export default function App() {
  const [view, setView] = useState("overview");
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [mode, setMode] = useState("single");
  const [recipient, setRecipient] = useState("");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [deliveryMode, setDeliveryMode] = useState("immediate");
  const [scheduleDate, setScheduleDate] = useState("");
  const [scheduleTime, setScheduleTime] = useState("");
  const [result, setResult] = useState(null);
  const [formError, setFormError] = useState("");
  const lastSubmission = useRef(null);
  const historyKey = apiConfig.historyPath ? ["email-records", apiConfig.baseUrl, apiConfig.historyPath] : null;
  const healthKey = apiConfig.healthPath ? ["api-health", apiConfig.baseUrl, apiConfig.healthPath] : null;
  const { data: records = [], error: historyError, isLoading: historyLoading, mutate: refreshHistory } = useSWR(historyKey, () => fetchEmailRecords(apiConfig));
  const { data: health, error: healthError, mutate: refreshHealth } = useSWR(healthKey, () => checkHealth(apiConfig), { shouldRetryOnError: false, revalidateOnFocus: false });
  const hasAnyRoute = Boolean(apiConfig.healthPath || apiConfig.historyPath || apiConfig.sendPath || apiConfig.schedulePath);
  const missingRoutes = [
    !apiConfig.healthPath && "VITE_API_HEALTH_PATH",
    !apiConfig.historyPath && "VITE_API_EMAILS_PATH",
    !apiConfig.sendPath && "VITE_API_SEND_PATH",
    !apiConfig.schedulePath && "VITE_API_SCHEDULE_PATH",
  ].filter(Boolean);

  async function refreshData() {
    const pending = [];
    if (historyKey) pending.push(refreshHistory());
    if (healthKey) pending.push(refreshHealth());
    await Promise.allSettled(pending);
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setFormError("");
    setResult(null);
    const addressList = mode === "single" ? [recipient.trim()].filter(Boolean) : getRecipients(recipient);
    if (addressList.length === 0) {
      setFormError("Add at least one recipient email address.");
      return;
    }
    const invalid = addressList.find((email) => !validEmail.test(email));
    if (invalid) {
      setFormError(`“${invalid}” is not a valid email address. Check the address and try again.`);
      return;
    }
    if (!subject.trim() || !body.trim()) {
      setFormError("Add a subject and message before sending.");
      return;
    }

    const isScheduled = deliveryMode === "scheduled";
    const scheduledAt = isScheduled ? cairoWallTimeToDate(scheduleDate, scheduleTime) : null;
    if (isScheduled && !scheduledAt) {
      setFormError(`Choose a valid date and time in ${SCHEDULE_TIME_ZONE}.`);
      return;
    }
    if (isScheduled && scheduledAt.getTime() <= Date.now()) {
      setFormError(`The scheduled date and time must be in the future (${SCHEDULE_TIME_ZONE}).`);
      return;
    }

    const basePayload = mode === "single"
      ? { recipient_email: addressList[0], subject: subject.trim(), body: body.trim() }
      : { recipient_emails: addressList, subject: subject.trim(), body: body.trim() };
    const payload = isScheduled
      ? { ...basePayload, scheduled_at: scheduledAt.toISOString(), timezone: SCHEDULE_TIME_ZONE }
      : basePayload;
    const signature = JSON.stringify({ deliveryMode, payload });
    const idempotencyKey = lastSubmission.current?.signature === signature
      ? lastSubmission.current.key
      : makeIdempotencyKey();
    lastSubmission.current = { signature, key: idempotencyKey };

    setIsSending(true);
    try {
      const response = isScheduled
        ? await scheduleEmail(apiConfig, payload, idempotencyKey)
        : await sendEmail(apiConfig, payload, idempotencyKey);
      setResult({ type: isScheduled ? "scheduled" : "immediate", outcome: response.outcome, statusCode: response.statusCode, message: responseMessage(response.body) });
      if (historyKey) void refreshHistory();
    } catch (error) {
      if (isScheduled) {
        setResult({
          type: "scheduled",
          outcome: "failed",
          statusCode: error?.status || "—",
          message: error?.status
            ? responseMessage(error.body) || error.message
            : `The scheduling request did not receive a confirmation from the Flask API (${error.message}). Check API history before retrying.`,
        });
      } else if (error?.status) {
        setResult({ type: "immediate", outcome: classifySendResponse(error.status, error.body), statusCode: error.status, message: responseMessage(error.body) || error.message });
      } else {
        setResult({ type: "immediate", outcome: "uncertain", statusCode: "—", message: "The browser did not receive a response from the Flask API. The email may still have been processed. Check history or SMTP logs before retrying." });
      }
      if (historyKey) void refreshHistory();
    } finally {
      setIsSending(false);
    }
  }

  function navigate(nextView) {
    setView(nextView);
    setMobileMenuOpen(false);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  const refreshing = historyLoading;
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">Skip to main content</a>
      <Sidebar activeView={view} onNavigate={navigate} mobileOpen={mobileMenuOpen} onClose={() => setMobileMenuOpen(false)} />
      <div className="main-shell">
        <PageHeader view={view} onMenu={() => setMobileMenuOpen(true)} health={health} healthError={healthError} hasAnyRoute={hasAnyRoute} onRefresh={refreshData} refreshing={refreshing} onCompose={() => navigate("compose")} />
        <main className="main-content" id="main-content">
          {view === "overview" && <Overview records={records} historyConfigured={Boolean(apiConfig.historyPath)} historyLoading={historyLoading} historyError={historyError} missingRoutes={missingRoutes} onCompose={() => navigate("compose")} onHistory={() => navigate("history")} />}
          {view === "compose" && <ComposePage sendConfigured={Boolean(apiConfig.sendPath)} scheduleConfigured={Boolean(apiConfig.schedulePath)} onSubmit={handleSubmit} isSending={isSending} result={result} formError={formError} mode={mode} setMode={setMode} recipient={recipient} setRecipient={setRecipient} subject={subject} setSubject={setSubject} body={body} setBody={setBody} deliveryMode={deliveryMode} setDeliveryMode={(nextMode) => { setDeliveryMode(nextMode); setResult(null); setFormError(""); }} scheduleDate={scheduleDate} setScheduleDate={setScheduleDate} scheduleTime={scheduleTime} setScheduleTime={setScheduleTime} />}
          {view === "history" && <HistoryPage records={records} isLoading={historyLoading} error={historyError} historyConfigured={Boolean(apiConfig.historyPath)} onRefresh={refreshData} onCompose={() => navigate("compose")} />}
        </main>
        <footer className="app-footer"><span>MailFlow</span><span>Connected to your backend, not a mock dataset.</span></footer>
      </div>
      <div className="sr-only" aria-live="polite">{historyLoading ? "Loading email history" : ""}</div>
    </div>
  );
}
