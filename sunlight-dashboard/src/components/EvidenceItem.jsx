export default function EvidenceItem({ label, value, colorClass }) {
  return (
    <div className="evidence-item">
      <div className="label">{label}</div>
      <div className={`value ${colorClass || ''}`}>{value}</div>
    </div>
  );
}
