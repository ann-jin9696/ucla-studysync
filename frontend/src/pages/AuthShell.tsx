import type { ReactNode } from 'react';
import {
  Books,
  CalendarCheck,
  ChatsCircle,
  GraduationCap,
  NotePencil,
  Sparkle,
  UsersThree,
} from '@phosphor-icons/react';
import { Link } from 'react-router-dom';
import studySyncLogo from '../assets/studysync-logo.png';

type AuthShellProps = {
  children: ReactNode;
  eyebrow: string;
  title: string;
  subtitle: string;
  switchPrompt: string;
  switchLabel: string;
  switchTo: string;
};

export function AuthShell({
  children,
  eyebrow,
  title,
  subtitle,
  switchPrompt,
  switchLabel,
  switchTo,
}: AuthShellProps) {
  const services = [
    {
      icon: <UsersThree size={25} weight="duotone" />,
      title: 'Find study groups',
    },
    {
      icon: <CalendarCheck size={25} weight="duotone" />,
      title: 'Plan sessions',
    },
    {
      icon: <NotePencil size={25} weight="duotone" />,
      title: 'Share notes',
    },
    {
      icon: <Books size={25} weight="duotone" />,
      title: 'Review faster',
    },
  ];

  return (
    <main className="auth-page">
      <section className="auth-split auth-split-form">
        <div className="auth-panel">
          <div className="brand-cluster" aria-label="StudySync">
            <div className="brand-mark">
              <img src={studySyncLogo} alt="" />
            </div>
            <div>
              <p className="brand-kicker">
                <Sparkle size={13} weight="fill" />
                StudySync
              </p>
              <h1>{title}</h1>
            </div>
          </div>
          <p className="eyebrow">{eyebrow}</p>
          <p className="auth-subtitle">{subtitle}</p>
          {children}
          <p className="auth-switch">
            {switchPrompt} <Link to={switchTo}>{switchLabel}</Link>
          </p>
        </div>
      </section>

      <section className="auth-split auth-split-services">
        <aside className="classroom-card service-panel" aria-label="What StudySync provides">
          <div className="service-panel-header">
            <div className="animated-service-icon" aria-hidden="true">
              <GraduationCap size={42} weight="duotone" />
              <Sparkle className="orbit-sparkle one" size={15} weight="fill" />
              <Sparkle className="orbit-sparkle two" size={12} weight="fill" />
            </div>
            <div>
              <p className="eyebrow">What you can do</p>
              <h2>Study together, from match to materials.</h2>
            </div>
          </div>
          <p className="service-panel-copy">
            StudySync helps UCLA students find compatible classmates, plan sessions,
            and keep every group resource in one bright workspace.
          </p>
          <div className="service-grid">
            {services.map((service) => (
              <article className="service-item" key={service.title}>
                <div className="service-icon">{service.icon}</div>
                <h3>{service.title}</h3>
              </article>
            ))}
          </div>
          <div className="service-note">
            <ChatsCircle size={24} weight="duotone" />
            <span>Built for sunny study groups, shared notes, and calmer project weeks.</span>
          </div>
        </aside>
      </section>
    </main>
  );
}
