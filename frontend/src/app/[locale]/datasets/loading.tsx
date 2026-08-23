import { Card, CardContent, CardHeader, Skeleton } from '@/components/ui';

export default function DatasetsLoading() {
  return (
    <div className="space-y-8" aria-busy="true">
      <section className="space-y-4">
        <Skeleton className="h-3 w-40" />
        <Skeleton className="h-10 w-64 max-w-full" />
        <Skeleton className="h-4 w-full max-w-2xl" />
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {Array.from({ length: 6 }).map((_, index) => (
          <Card key={index}>
            <CardHeader>
              <Skeleton className="h-6 w-3/4" />
              <Skeleton className="h-3 w-full" />
            </CardHeader>

            <CardContent className="space-y-5">
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-2/3" />
            </CardContent>
          </Card>
        ))}
      </section>
    </div>
  );
}
