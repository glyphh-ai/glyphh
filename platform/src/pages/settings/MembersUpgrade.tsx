import { useNavigate } from 'react-router';
import { usePlans } from '@/api/queries';
import { Button, Icon } from '@/ui';
import styles from './MembersUpgrade.module.css';

/** Members on a plan for one: what members are for, and the plan that adds them. Only the admin can upgrade. */
export function MembersUpgrade({ isAdmin }: { isAdmin: boolean }) {
  const navigate = useNavigate();
  const plans = usePlans();
  const team = plans.data?.find((plan) => plan.limits.members === null || plan.limits.members > 1);
  const upgrade = team ? `Upgrade to the ${team.name} plan to add members.` : 'Upgrade your plan to add members.';

  return (
    <section className={styles.upgrade} aria-labelledby="members-upgrade-title">
      <span className={styles.icon}>
        <Icon name="team" size={44} />
      </span>
      <h1 id="members-upgrade-title" className={styles.title}>
        Members
      </h1>
      <p className={styles.text}>Invite members to work together in your organisation.</p>
      <p className={styles.text}>{isAdmin ? upgrade : `${upgrade.replace('Upgrade', 'Ask your admin to upgrade')}`}</p>
      {isAdmin && (
        <div className={styles.actions}>
          <Button variant="primary" onClick={() => navigate('/settings/billing')}>
            Upgrade
          </Button>
        </div>
      )}
    </section>
  );
}
