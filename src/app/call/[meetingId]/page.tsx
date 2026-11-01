import generateAvatarURI from "@/lib/avatar";
import { auth } from "@/lib/auth";
import CallView, {
  CallViewError,
  CallViewLoading,
} from "@/modules/call/ui/views/call-view";
import { getQueryClient, trpc } from "@/trpc/server";
import { dehydrate, HydrationBoundary } from "@tanstack/react-query";
import { headers } from "next/headers";
import { redirect } from "next/navigation";
import { Suspense } from "react";
import { ErrorBoundary } from "react-error-boundary";

type Props = {
  params: Promise<{
    meetingId: string;
  }>;
};

const Page = async ({ params }: Props) => {
  const session = await auth.api.getSession({
    headers: await headers(),
  });

  if (!session) redirect("/sign-in");

  const { meetingId } = await params;

  const queryClient = getQueryClient();


  await queryClient.prefetchQuery(
    trpc.meetings.getForCall.queryOptions({ id: meetingId })
  );

  return (
    <HydrationBoundary state={dehydrate(queryClient)}>
      <Suspense fallback={<CallViewLoading />}>
        <ErrorBoundary fallback={<CallViewError />}>
          <CallView
            meetingId={meetingId}
            user={{
              id: session.user.id,
              name: session.user.name,
              image:
                session.user.image ??
                generateAvatarURI({
                  seed: session.user.name,
                  variant: "initials",
                }),
            }}
          />
        </ErrorBoundary>
      </Suspense>
    </HydrationBoundary>
  );
};

export default Page;
