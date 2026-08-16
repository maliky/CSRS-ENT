import { useState, type FocusEventHandler } from "react";
import styles from "./ui.module.css";

type WorkloadUnit = "hours" | "days";

type WorkloadInputProps = {
  id: string;
  valueDays: string;
  hoursPerDay: number;
  onValueChange: (days: string) => void;
  onFocus?: FocusEventHandler<HTMLInputElement>;
};

function normalizedDecimal(value: number): string {
  return value.toFixed(4).replace(/\.?0+$/, "");
}

function displayedValue(days: string, unit: WorkloadUnit, hoursPerDay: number) {
  if (!days) return "";
  const numericDays = Number(days);
  if (!Number.isFinite(numericDays)) return days;
  return normalizedDecimal(
    unit === "hours" ? numericDays * hoursPerDay : numericDays,
  );
}

export function WorkloadInput({
  id,
  valueDays,
  hoursPerDay,
  onValueChange,
  onFocus,
}: WorkloadInputProps) {
  const [unit, setUnit] = useState<WorkloadUnit>("hours");
  const safeHoursPerDay = hoursPerDay > 0 ? hoursPerDay : 8;

  return (
    <div className={styles.workloadInput}>
      <label htmlFor={id}>Charge estimée</label>
      <div className={styles.workloadFields}>
        <input
          id={id}
          type="number"
          min="0.0001"
          step="any"
          required
          value={displayedValue(valueDays, unit, safeHoursPerDay)}
          onFocus={onFocus}
          onChange={(event) => {
            const entered = event.currentTarget.value;
            if (!entered) {
              onValueChange("");
              return;
            }
            const numeric = Number(entered);
            if (!Number.isFinite(numeric)) return;
            onValueChange(
              normalizedDecimal(
                unit === "hours" ? numeric / safeHoursPerDay : numeric,
              ),
            );
          }}
        />
        <label className={styles.visuallyHidden} htmlFor={`${id}-unit`}>
          Unité
        </label>
        <select
          id={`${id}-unit`}
          aria-label="Unité"
          value={unit}
          onChange={(event) =>
            setUnit(event.currentTarget.value as WorkloadUnit)
          }
        >
          <option value="hours">heures</option>
          <option value="days">jours ouvrés</option>
        </select>
      </div>
      <small>1 jour ouvré = {normalizedDecimal(safeHoursPerDay)} heures</small>
    </div>
  );
}
