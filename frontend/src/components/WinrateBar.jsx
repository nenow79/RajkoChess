export default function WinrateBar({ white, draw, black }) {
  return (
    <div className="winrate-bar-container">
      <div className="winrate-white" style={{ width: `${white}%` }} title={`Białe: ${white}%`} />
      <div className="winrate-draw" style={{ width: `${draw}%` }} title={`Remis: ${draw}%`} />
      <div className="winrate-black" style={{ width: `${black}%` }} title={`Czarne: ${black}%`} />
    </div>
  );
}