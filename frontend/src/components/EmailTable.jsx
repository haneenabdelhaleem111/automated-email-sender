import { ArrowUpRight, MailOpen } from "lucide-react";
import {
  formatCairoDateTime,
  formatRecordDate,
  recordDateValue,
  recordScheduledDateValue,
  recordPreview,
  recordRecipients,
  recordStatus,
  recordSubject,
} from "../api";

const statusLabels = {
  success: "Sent",
  scheduled: "Scheduled",
  partial: "Partial",
  failed: "Failed",
  duplicate: "Duplicate",
  uncertain: "Uncertain",
  recorded: "Recorded",
};

function RecordDate({ record }) {
  const scheduledDate = recordScheduledDateValue(record);
  const label = scheduledDate ? formatCairoDateTime(scheduledDate) : formatRecordDate(recordDateValue(record));
  return <>{label}</>;
}

function StatusBadge({ record }) {
  const status = recordStatus(record);
  return <span className={`status-badge status-${status}`}><span className="status-badge-dot" />{statusLabels[status]}</span>;
}

function RecipientText({ record }) {
  const recipients = recordRecipients(record);
  if (recipients.length === 0) return <span className="muted-value">Not provided</span>;
  if (recipients.length === 1) return <span className="recipient-value">{recipients[0]}</span>;
  return <span className="recipient-value">{recipients[0]} <span className="recipient-extra">+{recipients.length - 1} more</span></span>;
}

function SubjectText({ record }) {
  const subject = recordSubject(record);
  const preview = recordPreview(record);
  return (
    <div className="subject-cell">
      <strong>{subject || "Subject not provided"}</strong>
      {preview && <span>{preview}</span>}
    </div>
  );
}

export function EmailTable({ records, emptyTitle = "No email activity yet", emptyDescription = "Emails recorded by your Flask API will appear here." }) {
  if (records.length === 0) {
    return (
      <div className="empty-state">
        <span className="empty-icon"><MailOpen size={22} strokeWidth={1.7} /></span>
        <h3>{emptyTitle}</h3>
        <p>{emptyDescription}</p>
      </div>
    );
  }

  return (
    <>
      <div className="table-wrap">
        <table className="email-table">
          <thead><tr><th scope="col">SUBJECT</th><th scope="col">RECIPIENT</th><th scope="col">STATUS</th><th scope="col">DATE / SCHEDULED</th></tr></thead>
          <tbody>
            {records.map((record, index) => (
              <tr key={record.id ?? record.email_id ?? `${recordDateValue(record) ?? "record"}-${index}`}>
                <td><SubjectText record={record} /></td>
                <td><RecipientText record={record} /></td>
                <td><StatusBadge record={record} /></td>
                <td><span className="date-value"><RecordDate record={record} /></span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="mobile-record-list">
        {records.map((record, index) => (
          <article className="mobile-record" key={record.id ?? record.email_id ?? `${recordDateValue(record) ?? "record"}-${index}`}>
            <div className="mobile-record-top"><StatusBadge record={record} /><span className="date-value"><RecordDate record={record} /></span></div>
            <SubjectText record={record} />
            <div className="mobile-record-recipient"><span>TO</span><RecipientText record={record} /></div>
          </article>
        ))}
      </div>
    </>
  );
}

export function RecentActivity({ records, onViewAll }) {
  const recent = records.slice(0, 4);
  return (
    <section className="panel activity-panel" aria-labelledby="activity-heading">
      <div className="panel-heading">
        <div><p className="eyebrow">YOUR LATEST SENDS</p><h2 id="activity-heading">Recent activity</h2></div>
        <button className="text-button" type="button" onClick={onViewAll}>View history <ArrowUpRight size={15} aria-hidden="true" /></button>
      </div>
      <EmailTable records={recent} emptyTitle="Your activity starts here" emptyDescription="Once your backend returns email records, the latest sends will show up in this space." />
    </section>
  );
}
