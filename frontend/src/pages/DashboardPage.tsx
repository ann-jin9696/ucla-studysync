import { Button, Card } from "antd";
import {
  CalendarCheck,
  ChatsCircle,
  NotePencil,
  SignOut,
  UsersThree,
  BinocularsIcon,
} from "@phosphor-icons/react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../components/AuthProvider";
import { MatchCard } from "../components/MatchCard";
import studySyncLogo from "../assets/studysync-logo.png";
import { ActivityCard } from "../components/ActivityCard";
import { ac } from "vitest/dist/chunks/reporters.nr4dxCkA.js";

export function DashboardPage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const mockMatches = [
    { id: 1, name: "Alice", matchedScore: 65, matchedCourse: "CS35L" },
    { id: 2, name: "Neel", matchedScore: 89, matchedCourse: "Math131A" },
    { id: 3, name: "Tobias", matchedScore: 96, matchedCourse: "CS35L" },
  ];

  const mockActivity = [
    {
      id: 1,
      name: "Alice",
      action: "Uploaded",
      target: "Midterm Review Notes",
      group: "CS35L",
      time: "1 hour ago",
    },
    {
      id: 2,
      name: "Neel",
      action: "Commented on",
      target: "HW2.pdf",
      group: "Math115A",
      time: "5 minutes ago",
    },
    {
      id: 3,
      name: "Tobias",
      action: "Said",
      target: "Are we free tomorrow?",
      group: "CS35L",
      time: "1 day ago",
    },
  ];

  async function handleLogout() {
    await logout();
    navigate("/login", { replace: true });
  }

  return (
    <main className="dashboard-page">
      <nav className="dashboard-nav">
        <div className="brand-cluster compact">
          <div className="brand-mark">
            <img src={studySyncLogo} alt="" />
          </div>
          <div>
            <p className="brand-kicker">StudySync</p>
            <strong>Dashboard</strong>
          </div>
        </div>
        <Button
          icon={<SignOut size={18} weight="bold" />}
          onClick={handleLogout}
        >
          Logout
        </Button>
      </nav>

      <section className="welcome-band">
        <p className="eyebrow">Sunny classroom mode</p>
        <h1>Hi, {user?.full_name ?? "Bruin"}.</h1>
        <p>
          Your account is ready. Profile setup, study group matching, and shared
          notes can plug into this dashboard next.
        </p>
      </section>

      <section className="activity-feed">
        <h2>Recent Activity</h2>
        {mockActivity.length > 0 ? (
          <div>
            {mockActivity.map((activity) => (
              <ActivityCard
                key={activity.id}
                name={activity.name}
                action={activity.action}
                target={activity.target}
                group={activity.group}
                time={activity.time}
              />
            ))}
          </div>
        ) : (
          <div className="empty-state-card">
            <BinocularsIcon size={32} weight="duotone" />
            <h3>No Recent Activity!</h3>
            <p>Join a study group to see what your classmates are up to!</p>
            <Button
              type="default"
              style={{ marginTop: "12px", borderRadius: "10px" }}
            >
              Find Groups
            </Button>
          </div>
        )}
      </section>

      <section className="matches-section">
        <h2>Your Top Matches</h2>
        {mockMatches.length > 0 ? (
          <div>
            {mockMatches.map((match) => (
              <MatchCard
                key={match.id}
                name={match.name}
                matchedScore={match.matchedScore}
                matchedCourse={match.matchedCourse}
              />
            ))}
          </div>
        ) : (
          <div className="empty-state-card">
            <UsersThree size={48} weight="duotone" />
            <h3>No matches yet!</h3>
            <p>Complete your profile, to find your study groups!</p>
            <Button type="primary">Finish Profile</Button>
          </div>
        )}
      </section>

      <section
        className="dashboard-grid"
        aria-label="Upcoming StudySync modules"
      >
        <Card>
          <UsersThree size={30} weight="duotone" />
          <h2>Profile setup</h2>
          <p>
            Add courses, availability, study goals, and collaboration style.
          </p>
        </Card>
        <Card>
          <CalendarCheck size={30} weight="duotone" />
          <h2>Group matching</h2>
          <p>Find classmates whose schedules and study habits fit yours.</p>
        </Card>
        <Card>
          <NotePencil size={30} weight="duotone" />
          <h2>Shared workspace</h2>
          <p>Keep notes, comments, and study materials in one calm place.</p>
        </Card>
        <Card>
          <ChatsCircle size={30} weight="duotone" />
          <h2>Group discussion</h2>
          <p>
            Leave questions and comments beside the notes your group shares.
          </p>
        </Card>
      </section>
    </main>
  );
}
