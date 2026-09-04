import { PartnersListPage } from "@/features/partners/partners-list-page";

export default function SuppliersPage() {
  return (
    <PartnersListPage
      partnerType="supplier"
      title="الموردون"
      description="قائمة موردي الشركة"
      createLabel="مورّد جديد"
    />
  );
}
