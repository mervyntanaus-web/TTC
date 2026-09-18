export default function Badge({ value }: { value: string }) {
  return <span className={`badge ${value}`}>{value.replace(/_/g, " ")}</span>;
}
