import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';

export default function ExperimentDetailLoading() {
  return (
    <main className="mx-auto w-full max-w-7xl space-y-6 px-4 py-6 sm:px-6 lg:px-8">
      <div className="space-y-3">
        <Skeleton className="h-5 w-36" />
        <Skeleton className="h-9 w-64" />
        <Skeleton className="h-5 w-80 max-w-full" />
      </div>

      {[3, 8, 4, 6].map((itemCount, sectionIndex) => (
        <Card key={sectionIndex}>
          <CardHeader>
            <Skeleton className="h-6 w-48" />
            <Skeleton className="h-4 w-72 max-w-full" />
          </CardHeader>

          <CardContent>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {Array.from({ length: itemCount }).map((_, itemIndex) => (
                <Skeleton key={itemIndex} className="h-24" />
              ))}
            </div>
          </CardContent>
        </Card>
      ))}
    </main>
  );
}
