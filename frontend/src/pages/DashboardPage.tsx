import { useState } from 'react';
import { Button, Card } from 'antd';
import {
  CalendarCheck,
  ChatsCircle,
  NotePencil,
  SignOut,
  UsersThree,
} from '@phosphor-icons/react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../components/AuthProvider';
import {
  WorkspaceModule,
  WorkspaceModuleMode,
} from '../components/WorkspaceModule';
import studySyncLogo from '../assets/studysync-logo.png';

export function DashboardPage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [activeModule, setActiveModule] = useState<WorkspaceModuleMode | null>(null);

  async function handleLogout() {
    await logout();
    navigate('/login', { replace: true });
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
        <Button icon={<SignOut size={18} weight="bold" />} onClick={handleLogout}>
          Logout
        </Button>
      </nav>

      <section className="welcome-band">
        <p className="eyebrow">Sunny classroom mode</p>
        <h1>Hi, {user?.full_name ?? 'Bruin'}.</h1>
        <p>
          Your account is ready. Profile setup, study group matching, and shared notes can
          plug into this dashboard next.
        </p>
      </section>

      <section className="dashboard-grid module-menu" aria-label="Upcoming StudySync modules">
        <Card>
          <UsersThree size={30} weight="duotone" />
          <h2>Profile setup</h2>
          <p>Add courses, availability, study goals, and collaboration style.</p>
        </Card>
        <Card>
          <CalendarCheck size={30} weight="duotone" />
          <h2>Group matching</h2>
          <p>Find classmates whose schedules and study habits fit yours.</p>
        </Card>
        <Card
          className={
            activeModule === 'workspace' ? 'module-card active-module-card' : 'module-card'
          }
          onClick={() => setActiveModule('workspace')}
          onKeyDown={(event) => {
            if (event.key === 'Enter' || event.key === ' ') {
              setActiveModule('workspace');
            }
          }}
          role="button"
          tabIndex={0}
        >
          <NotePencil size={30} weight="duotone" />
          <h2>Shared workspace</h2>
          <p>Keep notes, comments, and study materials in one calm place.</p>
        </Card>
        <Card
          className={
            activeModule === 'discussion'
              ? 'module-card active-module-card'
              : 'module-card'
          }
          onClick={() => setActiveModule('discussion')}
          onKeyDown={(event) => {
            if (event.key === 'Enter' || event.key === ' ') {
              setActiveModule('discussion');
            }
          }}
          role="button"
          tabIndex={0}
        >
          <ChatsCircle size={30} weight="duotone" />
          <h2>Group discussion</h2>
          <p>Leave questions and comments beside the notes your group shares.</p>
        </Card>
      </section>

      {activeModule && <WorkspaceModule mode={activeModule} />}
    </main>
  );
}
