import { Button, Card } from "antd";

interface MatchCardProps {
  name: string;
  matchedScore: number;
  matchedCourse: string;
}

export function MatchCard({
  name,
  matchedScore,
  matchedCourse,
}: MatchCardProps) {
  return (
    <Card style={{ marginBottom: "10px" }}>
      <h3 style={{ minWidth: "280px" }}>{name}</h3>
      <div className="match-score-percent">{matchedScore}% Matched</div>
      <p style={{ color: "#667c74" }}>{matchedCourse}</p>

      <Button
        type="default"
        style={{ marginTop: "10px", borderRadius: "12px" }}
      >
        View Profile
      </Button>
    </Card>
  );
}
