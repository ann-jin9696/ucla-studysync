import { Button, Card } from "antd";

interface ActivityCardProps {
  name: string;
  action: string;
  target: string;
  group: string;
  time: string;
  onView?: () => void;
}

export function ActivityCard({
  name,
  action,
  target,
  group,
  time,
  onView,
}: ActivityCardProps) {
  return (
    <Card
      className="activity-card"
      style={{ marginBottom: "5px" }}
      styles={{ body: { padding: "16px" } }}
    >
      <div className="activity-header">
        <p className="activity-name">{name}</p>
        <span className="activity-time">{time}</span>
      </div>

      <p className="activity-action-text">
        {action} <span className="activity-target-bold">{target}</span>
      </p>

      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <span className="activity-tag">#{group}</span>
        <Button
          aria-label={`View ${target}`}
          onClick={onView}
          size="small"
          type="text"
          style={{ color: "#3b9f89", fontWeight: 600 }}
        >
          View
        </Button>
      </div>
    </Card>
  );
}
