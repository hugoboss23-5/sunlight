import { useParams } from 'react-router-dom';
import { useCasePacket } from '../hooks/useApi';
import { fmtPct, formatDate } from '../utils/formatters';
import EvidenceItem from '../components/EvidenceItem';

export default function CaseDetail() {
  const { jobId } = useParams();
  const { data, loading, error } = useCasePacket(jobId);

  if (loading) return <div className="loading-container">Loading case packet...</div>;
  if (error) return <div className="loading-container error-msg">Error: {error}</div>;
  if (!data) return <div className="loading-container">No data found</div>;

  const result = data.result || {};

  return (
    <div className="fade-in">
      <div className="section-header">
        <span className="section-title">Case Detail</span>
        <span className="section-badge">{data.status}</span>
      </div>

      <div className="card" style={{ marginBottom: 'var(--space-xl)' }}>
        <h4 style={{ marginBottom: 'var(--space-md)', color: 'var(--text-primary)' }}>
          Job: {data.job_id}
        </h4>

        <div className="evidence-grid">
          <EvidenceItem label="Status" value={data.status} colorClass={data.status === 'COMPLETED' ? 'green' : 'amber'} />
          <EvidenceItem label="Progress" value={`${data.progress_pct}%`} />
          <EvidenceItem label="Created" value={formatDate(data.created_at)} />
          <EvidenceItem label="Completed" value={data.completed_at ? formatDate(data.completed_at) : '\u2014'} />
        </div>

        {data.progress_msg && (
          <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginTop: 'var(--space-md)' }}>
            {data.progress_msg}
          </div>
        )}
      </div>

      {result && Object.keys(result).length > 0 && (
        <div className="card">
          <div className="section-header">
            <span className="section-title">Results</span>
          </div>
          <div className="evidence-grid">
            {result.total_scored != null && <EvidenceItem label="Total Scored" value={result.total_scored} />}
            {result.red_count != null && <EvidenceItem label="RED" value={result.red_count} colorClass="red" />}
            {result.yellow_count != null && <EvidenceItem label="YELLOW" value={result.yellow_count} colorClass="amber" />}
            {result.green_count != null && <EvidenceItem label="GREEN" value={result.green_count} colorClass="green" />}
            {result.avg_confidence != null && <EvidenceItem label="Avg Confidence" value={fmtPct(result.avg_confidence)} />}
            {result.processing_time_seconds != null && <EvidenceItem label="Processing Time" value={`${result.processing_time_seconds}s`} />}
          </div>
        </div>
      )}
    </div>
  );
}

