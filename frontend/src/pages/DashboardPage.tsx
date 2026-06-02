import { type KeyboardEvent, useCallback, useEffect, useState } from "react";
import { Alert, Button, Card, Spin, message } from "antd";
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
import { ActivityCard } from "../components/ActivityCard";
import { GroupMatchingModule } from "../components/GroupMatchingModule";
import { ProfileSetupModule } from "../components/ProfileSetupModule";
import { useProfile } from "../components/ProfileProvider";
import {
  WorkspaceModule,
  WorkspaceModuleMode,
} from "../components/WorkspaceModule";
import { groupApi, type GroupActivity, type PendingApplication } from "../api";
import { parseApiTimestamp } from "../dateTime";
import { getMissingProfileSections } from "../profileOptions";
import studySyncLogo from "../assets/studysync-logo.png";

type DashboardModuleMode = "profile" | "matching" | WorkspaceModuleMode;
type WorkspaceTarget = {
  groupId: number;
  documentId: number;
  activityId: string;
  requestId: number;
};

function activityAction(activity: GroupActivity) {
  return activity.activity_type === "comment_added" ? "Commented on" : "Uploaded";
}

function formatRelativeTime(value: string) {
  const deltaSeconds = Math.round((parseApiTimestamp(value).getTime() - Date.now()) / 1000);
  const units: Array<[Intl.RelativeTimeFormatUnit, number]> = [
    ["year", 60 * 60 * 24 * 365],
    ["month", 60 * 60 * 24 * 30],
    ["week", 60 * 60 * 24 * 7],
    ["day", 60 * 60 * 24],
    ["hour", 60 * 60],
    ["minute", 60],
  ];
  const formatter = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });

  for (const [unit, secondsPerUnit] of units) {
    if (Math.abs(deltaSeconds) >= secondsPerUnit) {
      return formatter.format(Math.round(deltaSeconds / secondsPerUnit), unit);
    }
  }

  return "just now";
}

export function DashboardPage() {
  const { user, logout } = useAuth();
  const { profile } = useProfile();
  const navigate = useNavigate();
  const [messageApi, contextHolder] = message.useMessage();
  const [activeModule, setActiveModule] = useState<DashboardModuleMode | null>(null);
  const [workspaceTarget, setWorkspaceTarget] = useState<WorkspaceTarget | null>(null);
  const [activities, setActivities] = useState<GroupActivity[]>([]);
  const [loadingActivities, setLoadingActivities] = useState(true);
  const [activityError, setActivityError] = useState<string | null>(null);
  const [activityExpanded, setActivityExpanded] = useState(false);
  const [pendingApplications, setPendingApplications] = useState<PendingApplication[]>([]);
  const [loadingApplications, setLoadingApplications] = useState(true);
  const [applicationsExpanded, setApplicationsExpanded] = useState(false);
  const [decidingId, setDecidingId] = useState<number | null>(null);
  const missingSections = getMissingProfileSections(profile);

  const loadActivities = useCallback(async () => {
    setLoadingActivities(true);
    setActivityError(null);
    try {
      setActivities(await groupApi.listActivity());
    } catch (error) {
      setActivityError(
        error instanceof Error ? error.message : "Could not load recent activity.",
      );
    } finally {
      setLoadingActivities(false);
    }
  }, []);

  const loadPendingApplications = useCallback(async () => {
    setLoadingApplications(true);
    try {
      setPendingApplications(await groupApi.listPendingApplications());
    } catch {
      // silently fail — not critical
    } finally {
      setLoadingApplications(false);
    }
  }, []);

  async function handleDecision(app: PendingApplication, decision: "approve" | "reject") {
    setDecidingId(app.id);
    try {
      if (decision === "approve") {
        await groupApi.approveJoinRequest(app.group_id, app.id);
        messageApi.success(`${app.user_name} approved.`);
      } else {
        await groupApi.rejectJoinRequest(app.group_id, app.id);
        messageApi.success(`${app.user_name} rejected.`);
      }
    } catch (error) {
      messageApi.error(
        error instanceof Error ? error.message : "Could not update application.",
      );
    } finally {
      await loadPendingApplications();
      setDecidingId(null);
    }
  }

  async function handleLogout() {
    await logout();
    navigate("/login", { replace: true });
  }

  function moduleCardClass(moduleName: DashboardModuleMode) {
    return activeModule === moduleName
      ? "module-card active-module-card"
      : "module-card";
  }

  function handleModuleKeyDown(
    event: KeyboardEvent,
    moduleName: DashboardModuleMode,
  ) {
    if (event.key === "Enter" || event.key === " ") {
      selectModule(moduleName);
    }
  }

  function selectModule(moduleName: DashboardModuleMode) {
    setWorkspaceTarget(null);
    setActiveModule(moduleName);
  }

  function viewActivity(activity: GroupActivity) {
    setWorkspaceTarget((currentTarget) => ({
      groupId: activity.group_id,
      documentId: activity.document_id,
      activityId: activity.id,
      requestId: (currentTarget?.requestId ?? 0) + 1,
    }));
    setActiveModule(
      activity.activity_type === "comment_added" ? "discussion" : "workspace",
    );
  }

  useEffect(() => {
    void loadActivities();
    void loadPendingApplications();
  }, [loadActivities, loadPendingApplications]);

  const visibleApplications = applicationsExpanded
    ? pendingApplications
    : pendingApplications.slice(0, 3);

  return (
    <main className="dashboard-page">
      {contextHolder}
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
        <div className="dashboard-actions">
          <Button
            icon={<SignOut size={18} weight="bold" />}
            onClick={handleLogout}
          >
            Logout
          </Button>
        </div>
      </nav>

      <section className="welcome-band">
        <p className="eyebrow">Sunny classroom mode</p>
        <h1>Hi, {user?.full_name ?? "Bruin"}.</h1>
      </section>

      {profile && !profile.is_complete && (
        <Alert
          action={
            <Button onClick={() => selectModule("profile")} type="primary">
              Finish profile
            </Button>
          }
          className="profile-reminder dashboard-reminder"
          description={`Still missing: ${missingSections.join(", ")}.`}
          message="Finish your profile for better group matches"
          showIcon
          type="warning"
        />
      )}

      <div className="dashboard-feed-row">
      <section className="activity-feed">
        <h2>Pending Applications</h2>
        <Spin spinning={loadingApplications}>
          {pendingApplications.length > 0 ? (
            <div>
              {visibleApplications.map((app) => (
                <Card
                  key={app.id}
                  className="activity-card"
                  styles={{ body: { padding: "16px" } }}
                >
                  <div className="activity-header">
                    <p className="activity-name">{app.user_name}</p>
                    <span className="activity-time">{formatRelativeTime(app.created_at)}</span>
                  </div>
                  <p className="activity-action-text">
                    Applied to <span className="activity-target-bold">{app.group_name}</span>
                  </p>
                  <div className="activity-footer">
                    <span className="activity-tag">#{app.course_code}</span>
                    <div className="activity-actions">
                      <Button
                        size="small"
                        type="primary"
                        loading={decidingId === app.id}
                        onClick={() => handleDecision(app, "approve")}
                      >
                        Approve
                      </Button>
                      <Button
                        size="small"
                        type="primary"
                        danger
                        loading={decidingId === app.id}
                        onClick={() => handleDecision(app, "reject")}
                      >
                        Reject
                      </Button>
                    </div>
                  </div>
                </Card>
              ))}
              {pendingApplications.length > 3 && (
                <Button
                  type="link"
                  onClick={() => setApplicationsExpanded((prev) => !prev)}
                >
                  {applicationsExpanded
                    ? "Show less"
                    : `Show all ${pendingApplications.length}`}
                </Button>
              )}
            </div>
          ) : (
            <div className="empty-state-card">
              <BinocularsIcon size={32} weight="duotone" />
              <h3>No pending applications</h3>
              <p>When someone applies to join your group, it will appear here.</p>
            </div>
          )}
        </Spin>
      </section>

      <section className="activity-feed">
        <h2>Recent Activity</h2>
        {activityError && (
          <Alert
            className="dashboard-reminder"
            message={activityError}
            showIcon
            type="warning"
          />
        )}
        <Spin spinning={loadingActivities}>
          {activities.length > 0 ? (
            <div>
              {(activityExpanded ? activities : activities.slice(0, 3)).map((activity) => (
                <ActivityCard
                  key={activity.id}
                  name={activity.actor_name}
                  action={activityAction(activity)}
                  target={activity.document_title}
                  group={`${activity.group_name} · ${activity.course_code}`}
                  time={formatRelativeTime(activity.occurred_at)}
                  onView={() => viewActivity(activity)}
                />
              ))}
              {activities.length > 3 && (
                <Button
                  type="link"
                  onClick={() => setActivityExpanded((prev) => !prev)}
                >
                  {activityExpanded ? "Show less" : `Show all ${activities.length}`}
                </Button>
              )}
            </div>
          ) : (
            <div className="empty-state-card">
              <BinocularsIcon size={32} weight="duotone" />
              <h3>No recent activity</h3>
              <p>Join or create a group to see shared files and comments here.</p>
              <Button
                onClick={() => selectModule("matching")}
                type="default"
              >
                Find Groups
              </Button>
            </div>
          )}
        </Spin>
      </section>
      </div>

      <section
        className="dashboard-grid module-menu"
        aria-label="Upcoming StudySync modules"
      >
        <Card
          className={moduleCardClass("profile")}
          onClick={() => selectModule("profile")}
          onKeyDown={(event) => handleModuleKeyDown(event, "profile")}
          aria-pressed={activeModule === "profile"}
          role="button"
          tabIndex={0}
        >
          <UsersThree size={30} weight="duotone" />
          <h2>Profile setup</h2>
          <p>Add courses, quarters, lecture numbers, goals, pace, and group size.</p>
        </Card>
        <Card
          className={moduleCardClass("matching")}
          onClick={() => selectModule("matching")}
          onKeyDown={(event) => handleModuleKeyDown(event, "matching")}
          aria-pressed={activeModule === "matching"}
          role="button"
          tabIndex={0}
        >
          <CalendarCheck size={30} weight="duotone" />
          <h2>Group matching</h2>
          <p>Browse course groups, filter by fit, and apply to join.</p>
        </Card>
        <Card
          className={moduleCardClass("workspace")}
          onClick={() => selectModule("workspace")}
          onKeyDown={(event) => handleModuleKeyDown(event, "workspace")}
          aria-pressed={activeModule === "workspace"}
          role="button"
          tabIndex={0}
        >
          <NotePencil size={30} weight="duotone" />
          <h2>Shared workspaces</h2>
          <p>Keep notes, comments, and study materials in one calm place.</p>
        </Card>
        <Card
          className={moduleCardClass("discussion")}
          onClick={() => selectModule("discussion")}
          onKeyDown={(event) => handleModuleKeyDown(event, "discussion")}
          aria-pressed={activeModule === "discussion"}
          role="button"
          tabIndex={0}
        >
          <ChatsCircle size={30} weight="duotone" />
          <h2>Group discussion</h2>
          <p>
            Leave questions and comments beside the notes your group shares.
          </p>
        </Card>
      </section>

      {activeModule === "profile" && <ProfileSetupModule />}
      {activeModule === "matching" && <GroupMatchingModule />}
      {(activeModule === "workspace" || activeModule === "discussion") && (
        <WorkspaceModule
          mode={activeModule}
          initialGroupId={workspaceTarget?.groupId ?? null}
          initialDocumentId={workspaceTarget?.documentId ?? null}
          focusActivityId={workspaceTarget?.activityId ?? null}
          focusRequestId={workspaceTarget?.requestId ?? 0}
          onActivityChange={loadActivities}
        />
      )}
    </main>
  );
}
