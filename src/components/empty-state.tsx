"use client";

import Image from "next/image";
import React from "react";
type EmptyStateProps = {
  title: string;
  description: string;
  image?: string;
};

const EmptyState = ({ title, description, image }: EmptyStateProps) => {
  return (
    <div className="flex flex-col items-center justify-center gap-y-6 bg-background rounded-lg p-10 shadow-sm">
      <Image src={image ?? "/empty.svg"} width={240} height={240} alt="No Agents SVG" />
      <div className="flex flex-col gap-y-6 max-w-md mx-auto text-center">
        <h6 className="text-lg font-medium">{title}</h6>
        <p className="text-sm text-muted-foreground">{description}</p>
      </div>
    </div>
  );
};

export default EmptyState;
