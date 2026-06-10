import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import React from "react";
import { useTranslation } from "react-i18next";
import { View } from "react-native";

import { AppButton } from "../../components/AppButton";
import { AppText } from "../../components/AppText";
import { SpacingToken } from "../../designSystem/generated/spacing";
import type { HomeStackParamList } from "../../navigation/types";
import { useAppTheme } from "../../theme/ThemeContext";
import { useThemedStyles } from "../../theme/useThemedStyles";

type Props = NativeStackScreenProps<HomeStackParamList, "HomeDetail">;

export function HomeDetailScreen({ navigation, route }: Props) {
  const { t } = useTranslation();
  const { colors } = useAppTheme();
  const styles = useThemedStyles(c => ({
    container: {
      flex: 1,
      padding: SpacingToken.spacing_value_4,
      gap: SpacingToken.spacing_value_2_5,
      backgroundColor: c.background,
    },
  }));

  const { itemId, title } = route.params;

  return (
    <View style={styles.container}>
      <AppText variant="headingSm" color="text1">
        {t("homeDetail.title")}
      </AppText>
      <AppText variant="bodyMd" color="text2">
        {t("homeDetail.itemId", { id: itemId })}
      </AppText>
      {title ? (
        <AppText variant="bodyMd" color="text2">
          {t("homeDetail.titleMeta", { title })}
        </AppText>
      ) : null}

      <AppButton
        label={t("homeDetail.goBack")}
        onPress={() => navigation.goBack()}
        style={{ backgroundColor: colors.success }}
      />

      <AppButton
        label={t("homeDetail.popToTop")}
        onPress={() => navigation.popToTop()}
        style={{ backgroundColor: colors.success }}
      />

      <AppButton
        label={t("homeDetail.replaceMain")}
        onPress={() => navigation.replace("HomeMain")}
        style={{ backgroundColor: colors.success }}
      />

      <AppButton
        label={t("homeDetail.setParams")}
        onPress={() =>
          navigation.setParams({ title: t("homeDetail.updatedTitle") })
        }
        style={{ backgroundColor: colors.success }}
      />
    </View>
  );
}
