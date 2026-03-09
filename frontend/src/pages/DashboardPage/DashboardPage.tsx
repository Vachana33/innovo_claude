import styles from "./DashboardPage.module.css";

export default function DashboardPage() {
  return (
    <div className={styles.container}>
      <header className={styles.header}>
        <h1 className={styles.title}>Dashboard</h1>
        <p className={styles.subtitle}>Welcome to Innovo Agent</p>
      </header>
      <div className={styles.content}>
        <p className={styles.placeholder}>
          Dashboard overview and statistics will be displayed here.
        </p>
      </div>
    </div>
  );
}
