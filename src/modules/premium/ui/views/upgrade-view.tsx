"use client";

import ErrorState from '@/components/error-state';
import LoadingState from '@/components/loading-state';
import { authClient } from '@/lib/auth-client';
import { useTRPC } from '@/trpc/client';
import { useSuspenseQuery } from '@tanstack/react-query';
import React from 'react'
import PricingCard from '../components/pricing-card';

const UpgradeView = () => {
    const trpc = useTRPC();
    const { data: products } = useSuspenseQuery(trpc.premium.getProducts.queryOptions());

    const { data: currentSubscription } = useSuspenseQuery(
        trpc.premium.getCurrentSubscription.queryOptions()
    );

    return (
        <div className='flex-1 py-4 px-4 md:px-8 flex flex-col gap-y-10'>
            <div className="mt-4 flex-1 flex flex-col gap-y-10 items-center">
                <h5 className='font-medium text-2xl md:text-3xl'>
                    You are on the {" "}
                    <span className='font-semibold text-primary'>{currentSubscription?.name ?? "Free"}</span>{" "}plan
                </h5>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    {products.map((product) => {
                        const isCurrentProduct = currentSubscription?.id === product.id;
                        const isPremium = !!currentSubscription;

                        let buttonText = "Upgrade";
                        let onClick = () => authClient.checkout({ products: [product.id] });

                        if (isCurrentProduct) {
                            buttonText = "Manage";
                            onClick = () => authClient.customer.portal();
                        } else if (isPremium) {
                            buttonText = "Change Plan";
                            onClick = () => authClient.customer.portal();
                        }

                        const firstPrice = product.prices[0];
                        const recurringInterval = product.recurring_interval ?? "recurring";
                        const priceAmount = firstPrice.amount_type === "fixed" ? firstPrice.price_amount / 100 : 0;

                        return (
                            <PricingCard key={product.id} buttonText={buttonText} onClick={onClick} variant={
                                product.metadata.variant === "highlighted" ? "highlighted" : "default"}
                                title={product.name}
                                description={product.description || ""}
                                priceSuffix={`/${recurringInterval}`}
                                price={priceAmount}
                                features={product.benefits.map((benefit) => benefit.description)}
                            />
                        )
                    })}
                </div>
            </div>
        </div>
    )
}

export const UpgradeViewLoading = () => {
    return (
        <LoadingState
            title="Loading"
            description="This may take a few seconds..."
        />
    );
};

export const UpgradeViewError = () => {
    return (
        <ErrorState
            title="Error"
            description="Please try again later!"
        />
    );
};

export default UpgradeView