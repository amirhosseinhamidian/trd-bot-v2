import { RouteLoadingState } from '@/components/ui';

export default function ExperimentDetailLoading() {
  return (
    <RouteLoadingState
      variant="detail"
      className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 lg:px-8"
    />
  );
}
