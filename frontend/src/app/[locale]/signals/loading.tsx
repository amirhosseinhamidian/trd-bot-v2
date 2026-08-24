import { Card, CardContent, CardHeader, Skeleton } from '@/components/ui';

export default function SignalsLoading() {
  return (
    <div className="space-y-8" aria-busy="true">
      <section className="space-y-4">
        <Skeleton className="h-3 w-56" />
        <Skeleton className="h-10 w-72 max-w-full" />
        <Skeleton className="h-4 w-full max-w-3xl" />
        <Skeleton className="h-20 w-full" />
      </section>

      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-52" />
          <Skeleton className="h-4 w-96 max-w-full" />
        </CardHeader>

        <CardContent className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 5 }).map((_, index) => (
            <Skeleton key={index} className="h-11" />
          ))}
        </CardContent>
      </Card>

      <section className="grid gap-4 lg:grid-cols-2">
        {Array.from({ length: 4 }).map((_, index) => (
          <Card key={index}>
            <CardHeader>
              <Skeleton className="h-6 w-48" />
              <Skeleton className="h-4 w-full" />
            </CardHeader>

            <CardContent className="space-y-4">
              <Skeleton className="h-24 w-full" />
              <Skeleton className="h-20 w-full" />
              <Skeleton className="h-24 w-full" />
            </CardContent>
          </Card>
        ))}
      </section>
    </div>
  );
}
