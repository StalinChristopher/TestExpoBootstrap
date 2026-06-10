import { DrawerActions } from "@react-navigation/native";
import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import { FlatList, StyleSheet, View } from "react-native";

import type { Post } from "../../api/types/api";
import { AppButton } from "../../components/AppButton";
import { AppText } from "../../components/AppText";
import { TopBar } from "../../components/TopBar";
import { APP_DISPLAY_NAME } from "../../config/appDisplayName";
import { BorderRadiusToken } from "../../designSystem/generated/borderRadius";
import { SpacingToken } from "../../designSystem/generated/spacing";
import type { PostsMainCompositeProps } from "../../navigation/screenTypes";
import { useAppQuery } from "../../query/hooks/useAppQuery";
import { postService } from "../../services/postService";
import { useThemedStyles } from "../../theme/useThemedStyles";
import { InlineLoading } from "../../utils/loading";
import { ErrorStateView, EmptyStateView } from "../../utils/emptyErrorStates";

type Props = PostsMainCompositeProps;

const PostsScreen = ({ navigation }: Props) => {
  const { t } = useTranslation();
  const [useInvalidUrl, setUseInvalidUrl] = useState(false);

  const {
    data: posts,
    isPending,
    error,
    refetch,
  } = useAppQuery(["posts", useInvalidUrl], () =>
    useInvalidUrl
      ? Promise.reject(new Error("Network request failed"))
      : postService.getPosts(),
  );

  const styles = useThemedStyles(
    colors => ({
      root: { flex: 1, backgroundColor: colors.background },
      container: {
        flex: 1,
        padding: SpacingToken.spacing_value_4,
        backgroundColor: colors.background,
      },
      centered: {
        flex: 1,
        alignItems: "center",
        justifyContent: "center",
        padding: SpacingToken.spacing_value_4,
        backgroundColor: colors.background,
      },
      row: {
        paddingVertical: SpacingToken.spacing_value_3,
        borderBottomWidth: StyleSheet.hairlineWidth,
        borderBottomColor: colors.grayBackground,
      },
      toggleButton: {
        marginBottom: SpacingToken.spacing_value_3,
        alignSelf: "flex-start",
        backgroundColor: colors.grayBackground,
      },
    }),
    [],
  );

  const openMenu = () => navigation.dispatch(DrawerActions.openDrawer());

  const menuBar = (
    <TopBar topBarTitle={APP_DISPLAY_NAME} onMenuPress={openMenu} />
  );

  const handleRetry = () => {
    setUseInvalidUrl(false);
    void refetch();
  };

  if (isPending) {
    return (
      <View style={styles.root}>
        {menuBar}
        <View style={styles.centered}>
          <InlineLoading size="large" variant="spinner" />
        </View>
      </View>
    );
  }

  if (error) {
    return (
      <View style={styles.root}>
        {menuBar}
        <View style={styles.centered}>
          <ErrorStateView
            title={t("errorBoundary.title")}
            message="Unable to load posts. Please check your connection and try again."
            retryLabel={t("errorBoundary.tryAgain")}
            onRetry={handleRetry}
            layout="fullscreen"
          />
        </View>
      </View>
    );
  }

  const emptyPosts = posts?.length === 0;

  return (
    <View style={styles.root}>
      {menuBar}
      <View style={styles.container}>
        <AppText
          variant="headingSm"
          color="text1"
          style={{ marginBottom: SpacingToken.spacing_value_3 }}
        >
          {t("posts.title")}
        </AppText>
        <AppButton
          label={
            useInvalidUrl ? "Use valid URL" : "Simulate error (invalid URL)"
          }
          variant="ghost"
          accessibilityLabel="Toggle error state demo"
          onPress={() => setUseInvalidUrl(!useInvalidUrl)}
          style={[styles.toggleButton, { borderRadius: BorderRadiusToken.lg }]}
        />
        {emptyPosts ? (
          <EmptyStateView
            title={t("posts.empty")}
            description="There are no posts to display right now."
            layout="inline"
          />
        ) : (
          <FlatList<Post>
            data={posts ?? []}
            keyExtractor={item => String(item.id)}
            renderItem={({ item }) => (
              <View style={styles.row}>
                <AppText
                  variant="bodyMd"
                  color="text1"
                  style={{ fontWeight: "600" }}
                >
                  {item.title}
                </AppText>
                <AppText
                  variant="bodySm"
                  color="text2"
                  numberOfLines={2}
                  style={{
                    opacity: 0.75,
                    marginTop: SpacingToken.spacing_value_1,
                  }}
                >
                  {item.body}
                </AppText>
              </View>
            )}
          />
        )}
      </View>
    </View>
  );
};

export default PostsScreen;
