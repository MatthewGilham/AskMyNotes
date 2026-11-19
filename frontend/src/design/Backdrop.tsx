// The moving backdrop behind the whole app: three large, soft lights that
// drift slowly, under a fine grain. It is decoration only, so screen readers
// skip it and the pointer passes straight through it.
import styles from "./Backdrop.module.css";

export function Backdrop() {
  return (
    <div className={styles.backdrop} aria-hidden="true" data-backdrop>
      <div className={`${styles.glow} ${styles.first}`} />
      <div className={`${styles.glow} ${styles.second}`} />
      <div className={`${styles.glow} ${styles.third}`} />
      <div className={styles.grain} />
    </div>
  );
}
