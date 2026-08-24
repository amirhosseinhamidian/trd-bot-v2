import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';

export default function WalkForwardLoading() {
  return (
    <div className="space-y-8">
      <section className="space-y-3">
        <Skeleton className="h-4 w-52" />
        <Skeleton className="h-10 w-72 max-w-full" />
        <Skeleton className="h-5 w-160 max-w-full" />
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        {Array.from({ length: 4 }).map((_, index) => (
          <Card key={index}>
            <CardHeader>
              <Skeleton className="h-6 w-48" />
              <Skeleton className="h-4 w-72 max-w-full" />
            </CardHeader>

            <CardContent className="space-y-4">
              <div className="grid grid-cols-4 gap-3">
                {Array.from({ length: 4 }).map((_, metricIndex) => (
                  <Skeleton key={metricIndex} className="h-16" />
                ))}
              </div>

              <div className="grid grid-cols-2 gap-3">
                {Array.from({ length: 4 }).map((_, metricIndex) => (
                  <Skeleton key={metricIndex} className="h-20" />
                ))}
              </div>
            </CardContent>
          </Card>
        ))}
      </section>
    </div>
  );
}
