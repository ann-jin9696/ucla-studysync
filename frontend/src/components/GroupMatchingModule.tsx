import { useEffect, useMemo, useState } from 'react';
import { Button, Card, Empty, Input, Select, Spin, Tag, message } from 'antd';
import {
  CalendarCheck,
  CheckCircle,
  Funnel,
  PlusCircle,
  UserPlus,
  UsersThree,
  XCircle,
  SignOut,
} from '@phosphor-icons/react';
import type { GroupDirectoryEntry, JoinRequest, ProfileCourse } from '../api';
import { groupApi, matchingApi } from '../api';
import {
  EMPTY_PROFILE,
  PACE_OPTIONS,
  STUDY_GOAL_OPTIONS,
} from '../profileOptions';
import { useProfile } from './ProfileProvider';

const GROUP_SIZE_OPTIONS = [
  { label: 'Small (<5)', value: 'small' },
  { label: 'Medium (5-10)', value: 'medium' },
  { label: 'Large (>10)', value: 'large' },
];

const STUDY_GOAL_LABELS = new Map(
  STUDY_GOAL_OPTIONS.map((option) => [option.value, option.label]),
);
const PACE_LABELS = new Map(PACE_OPTIONS.map((option) => [option.value, option.label]));

function formatCourse(course: ProfileCourse) {
  return `${course.course_code} ${course.course_quarter} Lec ${course.lecture_number}`;
}

function formatGoal(value: string) {
  return STUDY_GOAL_LABELS.get(value) ?? value;
}

function formatPace(value: string | null) {
  if (!value) {
    return 'No pace yet';
  }
  return PACE_LABELS.get(value) ?? value;
}

export function GroupMatchingModule() {
  const { profile } = useProfile();
  const [messageApi, contextHolder] = message.useMessage();
  const activeProfile = profile ?? EMPTY_PROFILE;
  const [selectedUserCourseId, setSelectedUserCourseId] = useState<number | null>(
    activeProfile.courses[0]?.user_course_id ?? null,
  );
  const [directory, setDirectory] = useState<GroupDirectoryEntry[]>([]);
  const [studyGoalFilter, setStudyGoalFilter] = useState<string[]>([]);
  const [paceFilter, setPaceFilter] = useState<string | null>(null);
  const [groupSizeFilter, setGroupSizeFilter] = useState<string | null>(null);
  const [groupName, setGroupName] = useState('');
  const [applicantsByGroup, setApplicantsByGroup] = useState<
    Record<number, JoinRequest[]>
  >({});
  const [loadingDirectory, setLoadingDirectory] = useState(false);
  const [creatingGroup, setCreatingGroup] = useState(false);
  const [applyingGroupId, setApplyingGroupId] = useState<number | null>(null);
  const [leavingGroupId, setLeavingGroupId] = useState<number | null>(null);
  const [withdrawingRequestId, setWithdrawingRequestId] = useState<number | null>(null);
  const [decidingRequestId, setDecidingRequestId] = useState<number | null>(null);

  const selectedCourse = useMemo(
    () =>
      activeProfile.courses.find(
        (course) => course.user_course_id === selectedUserCourseId,
      ) ?? null,
    [activeProfile.courses, selectedUserCourseId],
  );

  const activePendingRequest = useMemo(
    () => directory.find((group) => group.pending_request_id !== null) ?? null,
    [directory],
  );

  async function loadOwnerRequests(groups: GroupDirectoryEntry[]) {
    const ownerGroups = groups.filter((group) => group.is_owner);
    if (ownerGroups.length === 0) {
      setApplicantsByGroup({});
      return;
    }

    try {
      const entries = await Promise.all(
        ownerGroups.map(async (group) => [
          group.id,
          await groupApi.listJoinRequests(group.id),
        ] as const),
      );
      setApplicantsByGroup(Object.fromEntries(entries));
    } catch (error) {
      messageApi.error(
        error instanceof Error ? error.message : 'Could not load applicants.',
      );
    }
  }

  async function loadDirectory(userCourseId: number) {
    setLoadingDirectory(true);
    try {
      const response = await matchingApi.listGroups(userCourseId, {
        studyGoals: studyGoalFilter,
        pacePreference: paceFilter,
        groupSize: groupSizeFilter,
      });
      setDirectory(response);
      await loadOwnerRequests(response);
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : 'Could not load groups.');
    } finally {
      setLoadingDirectory(false);
    }
  }

  async function handleCreateGroup() {
    if (!selectedUserCourseId) {
      return;
    }

    setCreatingGroup(true);
    try {
      await groupApi.create({
        user_course_id: selectedUserCourseId,
        name: groupName.trim() || undefined,
      });
      setGroupName('');
      messageApi.success('Group created.');
      await loadDirectory(selectedUserCourseId);
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : 'Could not create group.');
    } finally {
      setCreatingGroup(false);
    }
  }

  async function handleApply(groupId: number) {
    if (!selectedUserCourseId) {
      return;
    }

    setApplyingGroupId(groupId);
    try {
      await groupApi.apply(groupId);
      messageApi.success('Application sent.');
      await loadDirectory(selectedUserCourseId);
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : 'Could not apply.');
    } finally {
      setApplyingGroupId(null);
    }
  }

  async function handleLeave(groupId: number) {
    if (!selectedUserCourseId) {
      return;
    }

    setLeavingGroupId(groupId);
    try {
      await groupApi.leave(groupId);
      messageApi.success('Left group.');
      await loadDirectory(selectedUserCourseId);
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : 'Could not leave group.');
    } finally {
      setLeavingGroupId(null);
    }
  }

  async function handleWithdraw(groupId: number, requestId: number) {
    if (!selectedUserCourseId) {
      return;
    }

    setWithdrawingRequestId(requestId);
    try {
      await groupApi.withdrawJoinRequest(groupId, requestId);
      messageApi.success('Application withdrawn.');
      await loadDirectory(selectedUserCourseId);
    } catch (error) {
      messageApi.error(
        error instanceof Error ? error.message : 'Could not withdraw application.',
      );
    } finally {
      setWithdrawingRequestId(null);
    }
  }

  async function handleDecision(
    groupId: number,
    requestId: number,
    decision: 'approve' | 'reject',
  ) {
    if (!selectedUserCourseId) {
      return;
    }

    setDecidingRequestId(requestId);
    try {
      if (decision === 'approve') {
        await groupApi.approveJoinRequest(groupId, requestId);
        messageApi.success('Applicant approved.');
      } else {
        await groupApi.rejectJoinRequest(groupId, requestId);
        messageApi.success('Applicant rejected.');
      }
      await loadDirectory(selectedUserCourseId);
    } catch (error) {
      messageApi.error(
        error instanceof Error ? error.message : 'Could not update application.',
      );
    } finally {
      setDecidingRequestId(null);
    }
  }

  useEffect(() => {
    if (!activeProfile.courses.length) {
      setSelectedUserCourseId(null);
      return;
    }
    setSelectedUserCourseId((currentId) => {
      if (activeProfile.courses.some((course) => course.user_course_id === currentId)) {
        return currentId;
      }
      return activeProfile.courses[0].user_course_id;
    });
  }, [activeProfile.courses]);

  useEffect(() => {
    if (selectedUserCourseId) {
      void loadDirectory(selectedUserCourseId);
    } else {
      setDirectory([]);
      setApplicantsByGroup({});
    }
  }, [selectedUserCourseId, studyGoalFilter, paceFilter, groupSizeFilter]);

  return (
    <section className="workspace-shell group-matching-shell">
      {contextHolder}
      <div className="workspace-header">
        <div>
          <h2>Course groups</h2>
          <p>Pick a course, browse every group for it, and apply to one group at a time.</p>
          {activeProfile.courses.length > 0 && (
            <Select
              className="workspace-group-select"
              onChange={setSelectedUserCourseId}
              options={activeProfile.courses.map((course) => ({
                label: formatCourse(course),
                value: course.user_course_id,
              }))}
              value={selectedUserCourseId}
            />
          )}
        </div>
        <Card className="workspace-stat">
          <CalendarCheck size={28} weight="duotone" />
          <strong>{directory.length}</strong>
          <span>course groups</span>
        </Card>
      </div>

      {!selectedCourse ? (
        <Card className="workspace-tool-card">
          <Empty description="Add a course in your profile before browsing groups" />
        </Card>
      ) : (
        <div className="matching-layout">
          <div className="matching-sidebar">
            <Card className="workspace-tool-card matching-create-card">
              <div className="tool-card-heading">
                <PlusCircle size={24} weight="duotone" />
                <h2>Create a group</h2>
              </div>
              <p>
                Start a group for {formatCourse(selectedCourse)}. You will be its owner.
              </p>
              <Input
                maxLength={80}
                onChange={(event) => setGroupName(event.target.value)}
                placeholder="Group name"
                value={groupName}
              />
              <Button
                icon={<PlusCircle size={18} weight="bold" />}
                loading={creatingGroup}
                onClick={handleCreateGroup}
                type="primary"
              >
                Create group
              </Button>
            </Card>

            <Card className="workspace-tool-card matching-filter-card">
              <div className="tool-card-heading">
                <Funnel size={24} weight="duotone" />
                <h2>Filter groups</h2>
              </div>
              <Select
                allowClear
                mode="multiple"
                onChange={setStudyGoalFilter}
                options={STUDY_GOAL_OPTIONS}
                placeholder="Study goals"
                value={studyGoalFilter}
              />
              <Select
                allowClear
                onChange={(value) => setPaceFilter(value ?? null)}
                options={PACE_OPTIONS}
                placeholder="Average pace"
                value={paceFilter}
              />
              <Select
                allowClear
                onChange={(value) => setGroupSizeFilter(value ?? null)}
                options={GROUP_SIZE_OPTIONS}
                placeholder="Group size"
                value={groupSizeFilter}
              />
              <Button
                onClick={() => {
                  setStudyGoalFilter([]);
                  setPaceFilter(null);
                  setGroupSizeFilter(null);
                }}
              >
                Clear filters
              </Button>
            </Card>
          </div>

          <Card className="workspace-tool-card">
            <div className="tool-card-heading">
              <UsersThree size={24} weight="duotone" />
              <h2>Groups for {selectedCourse.course_code}</h2>
            </div>
            <Spin spinning={loadingDirectory}>
              {directory.length === 0 ? (
                <Empty description="No groups match these filters" />
              ) : (
                <div className="match-group-list">
                  {directory.map((group) => {
                    const applicants = applicantsByGroup[group.id] ?? [];
                    const pendingRequestId = group.pending_request_id;
                    const hasPendingElsewhere =
                      activePendingRequest !== null &&
                      activePendingRequest.id !== group.id;

                    return (
                      <article className="match-group-card directory-group-card" key={group.id}>
                        <div className="directory-group-main">
                          <div className="directory-group-title">
                            <div>
                              <h3>{group.name}</h3>
                              <p>
                                Owned by {group.owner_name} · {group.member_count} member
                                {group.member_count === 1 ? '' : 's'}
                              </p>
                            </div>
                            <div className="directory-group-tags">
                              {group.matches_preferred_group_size && (
                                <Tag color="green">Preferred size</Tag>
                              )}
                              <Tag>{GROUP_SIZE_OPTIONS.find(
                                (option) => option.value === group.group_size_bucket,
                              )?.label ?? group.group_size_bucket}</Tag>
                              <Tag>{formatPace(group.average_pace_preference)}</Tag>
                            </div>
                          </div>

                          <div className="directory-group-goals">
                            {group.top_study_goals.length === 0 ? (
                              <span>No study goals yet</span>
                            ) : (
                              group.top_study_goals.map((goal) => (
                                <Tag key={goal.value} color="cyan">
                                  {formatGoal(goal.value)} · {goal.count}
                                </Tag>
                              ))
                            )}
                          </div>

                          {group.pending_request_id && (
                            <p className="directory-pending-note">
                              Application pending.
                            </p>
                          )}

                          {group.is_owner && (
                            <div className="applicant-panel">
                              <strong>
                                Applicants
                                {group.pending_applicant_count > 0
                                  ? ` (${group.pending_applicant_count})`
                                  : ''}
                              </strong>
                              {applicants.length === 0 ? (
                                <p>No pending applicants.</p>
                              ) : (
                                applicants.map((request) => (
                                  <div className="applicant-row" key={request.id}>
                                    <span>{request.user_name}</span>
                                    <div>
                                      <Button
                                        icon={<CheckCircle size={16} weight="bold" />}
                                        loading={decidingRequestId === request.id}
                                        onClick={() =>
                                          handleDecision(group.id, request.id, 'approve')
                                        }
                                        size="small"
                                        type="primary"
                                      >
                                        Allow
                                      </Button>
                                      <Button
                                        icon={<XCircle size={16} weight="bold" />}
                                        loading={decidingRequestId === request.id}
                                        onClick={() =>
                                          handleDecision(group.id, request.id, 'reject')
                                        }
                                        size="small"
                                      >
                                        Disallow
                                      </Button>
                                    </div>
                                  </div>
                                ))
                              )}
                            </div>
                          )}
                        </div>

                        <div className="directory-group-action">
                          {group.is_member ? (
                            <>
                              {group.is_owner && <Tag color="gold">Owner</Tag>}
                              <Button
                                icon={<SignOut size={18} weight="bold" />}
                                loading={leavingGroupId === group.id}
                                onClick={() => handleLeave(group.id)}
                              >
                                Leave
                              </Button>
                            </>
                          ) : group.is_owner ? (
                            <Tag color="gold">Owner</Tag>
                          ) : pendingRequestId ? (
                            <>
                              <Tag color="orange">Pending</Tag>
                              <Button
                                icon={<XCircle size={18} weight="bold" />}
                                loading={withdrawingRequestId === pendingRequestId}
                                onClick={() => handleWithdraw(group.id, pendingRequestId)}
                              >
                                Withdraw
                              </Button>
                            </>
                          ) : (
                            <Button
                              disabled={hasPendingElsewhere}
                              icon={<UserPlus size={18} weight="bold" />}
                              loading={applyingGroupId === group.id}
                              onClick={() => handleApply(group.id)}
                              type="primary"
                            >
                              Apply
                            </Button>
                          )}
                        </div>
                      </article>
                    );
                  })}
                </div>
              )}
            </Spin>
          </Card>
        </div>
      )}
    </section>
  );
}
