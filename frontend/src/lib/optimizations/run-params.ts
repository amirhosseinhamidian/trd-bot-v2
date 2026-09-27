export type OptimizationSearchParams = Record<string, string | string[] | undefined>;

function getFirstValue(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

export function parseOptimizationExecutionId(
  searchParams: OptimizationSearchParams,
): string | undefined {
  const executionId = getFirstValue(searchParams.execution)?.trim();

  if (executionId === undefined || !/^optimization-[a-f0-9]{16}$/u.test(executionId)) {
    return undefined;
  }

  return executionId;
}
